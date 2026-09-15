from fastapi import APIRouter

from ..ensemble import ensemble_predict
from ..model_service import model_service
from ..rules import rule_based_score
from ..schemas import ScoreRequest, ScoreResponse

router = APIRouter(prefix="/api", tags=["scoring"])


@router.post("/score", response_model=ScoreResponse)
def score_subscriber(payload: ScoreRequest) -> ScoreResponse:
    raw = payload.model_dump()

    ml_result = model_service.score(raw)
    rule_score, triggered_rules, hard_block = rule_based_score(raw)
    ensemble_result = ensemble_predict(
        rule_score=rule_score, ml_score=ml_result["risk_score_0_100"] / 100.0, hard_block=hard_block
    )

    return ScoreResponse(
        **ml_result,
        rule_score=ensemble_result["rule_score"],
        ml_score=ensemble_result["ml_score"],
        final_score=ensemble_result["final_score"],
        decision=ensemble_result["decision"],
        triggered_rules=triggered_rules,
    )
