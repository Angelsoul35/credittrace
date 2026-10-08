"""CreditTrace HTTP API."""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from app.deps import get_service
from app.schemas import ApplicantIn, ScoreResponse, VerifyResponse
from app.service import ScoringService

app = FastAPI(
    title="CreditTrace",
    version="1.0.0",
    summary="Explainable credit-risk scoring with tamper-evident on-chain anchoring.",
    description=(
        "Scores microloan applications with an XGBoost model, explains every "
        "decision with SHAP, and anchors a keccak256 digest of each decision on "
        "an EVM registry so it can be independently verified later."
    ),
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/model", tags=["model"])
def model_info(service: ScoringService = Depends(get_service)) -> dict:
    return {"version": service.model.version, "metadata": service.model.metadata}


@app.post("/score", response_model=ScoreResponse, tags=["scoring"])
def score(
    applicant: ApplicantIn, service: ScoringService = Depends(get_service)
) -> ScoreResponse:
    result = service.score(applicant.model_dump())
    return ScoreResponse.model_validate(result)


@app.get("/decisions/{decision_id}", tags=["scoring"])
def get_decision(
    decision_id: str, service: ScoringService = Depends(get_service)
) -> dict:
    record = service.get(decision_id)
    if record is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return record


@app.get("/decisions/{decision_id}/verify", response_model=VerifyResponse, tags=["scoring"])
def verify_decision(
    decision_id: str, service: ScoringService = Depends(get_service)
) -> VerifyResponse:
    result = service.verify(decision_id)
    if result is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return VerifyResponse.model_validate(result)
