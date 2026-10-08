"""Feature contract for the credit-risk model.

A single source of truth for the columns the model consumes, shared by the
synthetic data generator, the training pipeline, the scoring service and the
request schema. Keeping it here means the API, the model and the tests can
never silently drift apart.
"""

from __future__ import annotations

NUMERIC_FEATURES: list[str] = [
    "age",
    "monthly_income",
    "loan_amount",
    "loan_term_months",
    "employment_length_years",
    "debt_to_income",
    "num_existing_loans",
    "num_late_payments_12m",
    "has_collateral",
]

CATEGORICAL_FEATURES: list[str] = [
    "region",
    "loan_purpose",
]

FEATURE_ORDER: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES

REGIONS: list[str] = ["andina", "caribe", "pacifica", "orinoquia", "amazonia"]
LOAN_PURPOSES: list[str] = [
    "working_capital",
    "inventory",
    "equipment",
    "education",
    "home_improvement",
    "emergency",
]

TARGET: str = "default"

# Human-readable labels used when turning SHAP contributions into decision
# reasons. The scoring API is useless to a credit officer if it only returns
# "num__debt_to_income = 0.73"; it must say what that means.
FEATURE_LABELS: dict[str, str] = {
    "age": "Applicant age",
    "monthly_income": "Monthly income",
    "loan_amount": "Requested loan amount",
    "loan_term_months": "Loan term (months)",
    "employment_length_years": "Employment length (years)",
    "debt_to_income": "Debt-to-income ratio",
    "num_existing_loans": "Number of existing loans",
    "num_late_payments_12m": "Late payments (last 12 months)",
    "has_collateral": "Collateral provided",
    "region": "Region",
    "loan_purpose": "Loan purpose",
}
