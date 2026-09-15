"""
Live scoring service for the PCRF Isolation Forest model.

This reproduces, exactly, the pipeline built across preprocess.ipynb and
Isolation_forest_new.ipynb:

  1. offer_name -> offer_frequency_encoding via a precomputed global lookup
     (preprocess.ipynb, "Offer name encoding" section).
  2. Feature vector assembled in the SAME column order the model was
     trained on (model.feature_names_in_), missing/inf values filled with
     the SAME per-column medians used at training time.
  3. raw anomaly_score = -model.score_samples(X)   (higher = more anomalous)
  4. risk_score_0_100 = percentile rank of anomaly_score against the
     ORIGINAL 615,027-row reference distribution (reference_scores.npy),
     NOT a standalone function of one record. This matches:
         anomaly_percentile = rank(anomaly_score, pct=True, ascending=True) * 100
     from Isolation_forest_new.ipynb cell 12.

Artifacts required (in app/artifacts/):
  - isolation_forest_model.pkl
  - feature_medians.json
  - offer_frequency_map.json
  - reference_scores.npy
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

ARTIFACT_DIR = Path(__file__).parent / "artifacts"

# Exact training feature order (must match model.feature_names_in_).
FEATURE_ORDER = [
    "sessions_per_day",
    "daily_usage_gb",
    "average_session_usage_gb",
    "total_duration_minutes",
    "average_session_duration_minutes",
    "total_input_gb",
    "total_output_gb",
    "offer_count",
    "Ratio",
    "offer_frequency_encoding",
]


class ModelService:
    def __init__(self) -> None:
        self.model = joblib.load(ARTIFACT_DIR / "isolation_forest_model.pkl")

        if list(self.model.feature_names_in_) != FEATURE_ORDER:
            raise RuntimeError(
                "Model feature order does not match FEATURE_ORDER. "
                f"Model expects: {list(self.model.feature_names_in_)}"
            )

        with open(ARTIFACT_DIR / "feature_medians.json") as f:
            self.medians: dict[str, float] = json.load(f)

        with open(ARTIFACT_DIR / "offer_frequency_map.json") as f:
            offer_rows = json.load(f)
        self.offer_frequency_map: dict[str, float] = {
            row["offer_name"]: float(row["offer_frequency_encoding"]) for row in offer_rows
        }
        # Fallback for an offer_name never seen during training: use the
        # median offer_frequency_encoding from the training medians file
        # rather than guessing 0 (which would look like an ultra-rare offer
        # and could distort the score).
        self.unknown_offer_encoding = float(self.medians["offer_frequency_encoding"])

        # Reference distribution of raw anomaly scores from the full
        # training set. Sorted once for fast percentile lookups.
        self.reference_scores = np.sort(np.load(ARTIFACT_DIR / "reference_scores.npy"))
        self.reference_n = len(self.reference_scores)

    def _clean(self, value: Optional[float], feature_name: str) -> float:
        """Replicate X.replace([inf,-inf], nan).fillna(X.median())."""
        if value is None:
            return self.medians[feature_name]
        try:
            v = float(value)
        except (TypeError, ValueError):
            return self.medians[feature_name]
        if math.isnan(v) or math.isinf(v):
            return self.medians[feature_name]
        return v

    def encode_offer(self, offer_name: Optional[str]) -> float:
        if not offer_name:
            return self.unknown_offer_encoding
        return self.offer_frequency_map.get(offer_name.strip(), self.unknown_offer_encoding)

    def build_feature_vector(self, raw: dict) -> list[float]:
        """
        raw: dict with keys matching the ALREADY-AGGREGATED daily feature
        set (same shape as one row before offer_frequency_encoding is
        attached): sessions_per_day, daily_usage_gb,
        average_session_usage_gb, total_duration_minutes,
        average_session_duration_minutes, total_input_gb, total_output_gb,
        offer_count, offer_name, and optionally Ratio (computed
        server-side from total_input_gb/total_output_gb if omitted).
        """
        total_input_gb = self._clean(raw.get("total_input_gb"), "total_input_gb")
        total_output_gb = self._clean(raw.get("total_output_gb"), "total_output_gb")

        ratio = raw.get("Ratio")
        if ratio is None:
            ratio = None if total_output_gb == 0 else total_input_gb / total_output_gb

        offer_frequency_encoding = self.encode_offer(raw.get("offer_name"))

        values = {
            "sessions_per_day": self._clean(raw.get("sessions_per_day"), "sessions_per_day"),
            "daily_usage_gb": self._clean(raw.get("daily_usage_gb"), "daily_usage_gb"),
            "average_session_usage_gb": self._clean(
                raw.get("average_session_usage_gb"), "average_session_usage_gb"
            ),
            "total_duration_minutes": self._clean(
                raw.get("total_duration_minutes"), "total_duration_minutes"
            ),
            "average_session_duration_minutes": self._clean(
                raw.get("average_session_duration_minutes"), "average_session_duration_minutes"
            ),
            "total_input_gb": total_input_gb,
            "total_output_gb": total_output_gb,
            "offer_count": self._clean(raw.get("offer_count"), "offer_count"),
            "Ratio": self._clean(ratio, "Ratio"),
            "offer_frequency_encoding": offer_frequency_encoding,
        }
        return [values[name] for name in FEATURE_ORDER]

    def percentile_rank(self, anomaly_score: float) -> float:
        """
        Same semantics as pandas .rank(method="average", pct=True,
        ascending=True) evaluated against the ORIGINAL reference set with
        the new point added, matching Isolation_forest_new.ipynb cell 12.
        """
        # Count of reference values <= new score (searchsorted 'right')
        # and < new score (searchsorted 'left'), across the reference set
        # PLUS the new point itself (n = reference_n + 1).
        left = np.searchsorted(self.reference_scores, anomaly_score, side="left")
        right = np.searchsorted(self.reference_scores, anomaly_score, side="right")
        n = self.reference_n + 1
        # average rank (1-indexed) of ties = midpoint of [left+1, right+1]
        avg_rank = (left + 1 + right + 1) / 2.0
        percentile = (avg_rank / n) * 100.0
        return round(min(100.0, max(0.0, percentile)), 6)

    def risk_level(self, score: float) -> str:
        if score >= 90:
            return "High Risk"
        if score >= 85:
            return "Medium Risk"
        if score >= 70:
            return "Low Risk"
        return "Normal"

    def score(self, raw: dict) -> dict:
        feature_vector = self.build_feature_vector(raw)
        x = pd.DataFrame([feature_vector], columns=FEATURE_ORDER)
        raw_score_samples = self.model.score_samples(x)[0]
        anomaly_score = -float(raw_score_samples)
        risk_score_0_100 = self.percentile_rank(anomaly_score)

        return {
            "risk_score_0_100": risk_score_0_100,
            "risk_level": self.risk_level(risk_score_0_100),
            "anomaly_score": round(anomaly_score, 6),
            "features_used": dict(zip(FEATURE_ORDER, feature_vector)),
        }

    def score_dataframe(self, df: pd.DataFrame, mode_offer_column: str = "mode_offer_name") -> pd.DataFrame:
        """
        Vectorized scoring for a whole batch of already-aggregated daily
        rows (e.g. one day's worth of new subscriber data). `df` must
        already have one row per (session_date, account_num,
        subscriber_id) with columns: sessions_per_day, daily_usage_gb,
        average_session_usage_gb, total_duration_minutes,
        average_session_duration_minutes, total_input_gb, total_output_gb,
        offer_count, Ratio, and a `mode_offer_column` holding the single
        most-used offer_name that day (used for frequency-encoding
        lookup -- NOT the same as a display "offer_name" that might be a
        comma-joined list of all offers used that day).

        Returns a copy of df with anomaly_score and risk_score_0_100
        columns added.
        """
        out = df.copy()

        for col in ["sessions_per_day", "daily_usage_gb", "average_session_usage_gb",
                    "total_duration_minutes", "average_session_duration_minutes",
                    "total_input_gb", "total_output_gb", "offer_count", "Ratio"]:
            series = pd.to_numeric(out[col], errors="coerce") if col in out.columns else pd.Series(np.nan, index=out.index)
            series = series.replace([np.inf, -np.inf], np.nan)
            out[col] = series.fillna(self.medians[col])

        out["offer_frequency_encoding"] = (
            out[mode_offer_column]
            .map(self.offer_frequency_map)
            .fillna(self.unknown_offer_encoding)
        )

        x = out[FEATURE_ORDER]
        raw_score_samples = self.model.score_samples(x)
        anomaly_score = -raw_score_samples

        # Vectorized percentile rank against the reference distribution:
        # for each new score, find its position among the (frozen)
        # reference scores. This mirrors percentile_rank() but avoids a
        # Python-level loop per row.
        left = np.searchsorted(self.reference_scores, anomaly_score, side="left")
        right = np.searchsorted(self.reference_scores, anomaly_score, side="right")
        n = self.reference_n + 1
        avg_rank = (left + 1 + right + 1) / 2.0
        risk_score_0_100 = np.clip((avg_rank / n) * 100.0, 0.0, 100.0).round(6)

        out["anomaly_score"] = anomaly_score.round(6)
        out["risk_score_0_100"] = risk_score_0_100
        return out


# Singleton, loaded once per process (Lambda container reuse-friendly).
model_service = ModelService()
