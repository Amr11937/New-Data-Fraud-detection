"""
Rule-based fraud scoring, ported from the Broadband FMS rule engine and
re-pointed at app/config/rules.yaml (PCRF's feature names/units).

Each rule: {feature, upper_limit, points}. A row's rule_score is the
sum of triggered rules' points, normalized by max_raw_score into 0-1.
"""
import os
from typing import Dict, List, Tuple

import yaml

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "rules.yaml")

_ACTIVE_RULE_NAMES = ["rule_01", "rule_02", "rule_03", "rule_04", "rule_05", "rule_06", "rule_07"]

_cfg: Dict | None = None


def load_rules() -> Dict:
    global _cfg
    if _cfg is None:
        with open(CONFIG_PATH, "r") as f:
            _cfg = yaml.safe_load(f)
    return _cfg


def rule_based_score(data: dict) -> Tuple[float, List[str], bool]:
    """
    data: dict with PCRF's aggregated daily feature names (same shape
    accepted by model_service.build_feature_vector): daily_usage_gb,
    total_input_gb, total_output_gb, average_session_usage_gb,
    sessions_per_day, offer_count, Ratio.

    Returns (normalized_score 0-1, triggered_rule_ids, hard_block).
    """
    cfg = load_rules()
    score = 0.0
    triggered: List[str] = []
    hard_block = False

    for rule_name in _ACTIVE_RULE_NAMES:
        if rule_name not in cfg:
            continue
        rule = cfg[rule_name]
        feature = rule["feature"]
        value = data.get(feature)
        value = 0.0 if value is None else float(value)
        if value > rule["upper_limit"]:
            score += rule["points"]
            triggered.append(rule_name)
            if rule.get("hard_block"):
                hard_block = True

    normalized_score = min(score / cfg.get("max_raw_score", 100), 1.0)
    return normalized_score, triggered, hard_block
