"""
Combines the rule engine's rule_score with the Isolation Forest's
ml_score into a final decision. Ported unchanged from Broadband FMS --
the weighting logic doesn't depend on which database or feature set
produced the two input scores.

    Rule engine  -> rule_score (0-1)
    Isolation Forest -> ml_score (0-1)  [ = risk_score_0_100 / 100 ]
    Weighted average -> final_score (0-1) -> decision
"""
from typing import Dict

RULE_WEIGHT = 0.40
ML_WEIGHT = 0.60

BLOCK_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.45


def ensemble_predict(rule_score: float, ml_score: float, hard_block: bool = False) -> Dict:
    if hard_block:
        return {
            "rule_score": round(rule_score, 4),
            "ml_score": round(ml_score, 4),
            "final_score": 1.0,
            "decision": "BLOCK",
        }

    final_score = RULE_WEIGHT * rule_score + ML_WEIGHT * ml_score

    if final_score >= BLOCK_THRESHOLD:
        decision = "BLOCK"
    elif final_score >= REVIEW_THRESHOLD:
        decision = "REVIEW"
    else:
        decision = "ALLOW"

    return {
        "rule_score": round(rule_score, 4),
        "ml_score": round(ml_score, 4),
        "final_score": round(final_score, 4),
        "decision": decision,
    }
