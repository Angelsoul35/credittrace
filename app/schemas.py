"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.ml.features import LOAN_PURPOSES, REGIONS


class ApplicantIn(BaseModel):
    """A microloan application. All fields are required and range-checked."""

    age: int = Field(ge=18, le=100)
    monthly_income: float = Field(gt=0, description="Monthly income (COP)")
    loan_amount: float = Field(gt=0, description="Requested principal (COP)")
    loan_term_months: int = Field(ge=1, le=120)
    employment_length_years: float = Field(ge=0, le=60)
    debt_to_income: float = Field(ge=0, le=3, description="Debt-to-income ratio")
    num_existing_loans: int = Field(ge=0, le=50)
    num_late_payments_12m: int = Field(ge=0, le=50)
    has_collateral: int = Field(ge=0, le=1)
    region: str
    loan_purpose: str

    @field_validator("region")
    @classmethod
    def _check_region(cls, v: str) -> str:
        if v not in REGIONS:
            raise ValueError(f"region must be one of {REGIONS}")
        return v

    @field_validator("loan_purpose")
    @classmethod
    def _check_purpose(cls, v: str) -> str:
        if v not in LOAN_PURPOSES:
            raise ValueError(f"loan_purpose must be one of {LOAN_PURPOSES}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "age": 34,
                "monthly_income": 3200000,
                "loan_amount": 6000000,
                "loan_term_months": 24,
                "employment_length_years": 5.0,
                "debt_to_income": 0.38,
                "num_existing_loans": 1,
                "num_late_payments_12m": 0,
                "has_collateral": 1,
                "region": "andina",
                "loan_purpose": "working_capital",
            }
        }
    }


class ReasonOut(BaseModel):
    feature: str
    label: str
    value: object
    contribution: float
    direction: Literal["increases_risk", "decreases_risk"]


class AnchorOut(BaseModel):
    enabled: bool
    anchored: bool
    digest: str
    tx_hash: str | None = None
    block_number: int | None = None
    contract_address: str | None = None
    already_anchored: bool = False


class ScoreResponse(BaseModel):
    decision_id: str
    model_version: str
    probability: float
    score_bps: int
    band: Literal["low", "medium", "high"]
    decision: Literal["approve", "review", "decline"]
    reasons: list[ReasonOut]
    anchor: AnchorOut


class OnChainOut(BaseModel):
    anchored: bool
    submitter: str | None = None
    timestamp: int = 0
    block_number: int = 0
    contract_address: str | None = None


class VerifyResponse(BaseModel):
    decision_id: str
    stored_digest: str
    recomputed_digest: str
    digest_matches: bool
    on_chain: OnChainOut
    status: Literal["verified", "digest_mismatch", "not_anchored", "chain_disabled"]
