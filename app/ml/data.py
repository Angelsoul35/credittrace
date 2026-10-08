"""Synthetic applicant generator.

The dataset is fully synthetic and deterministic: no real person, client or
institution is involved. Defaults are drawn from a latent logistic model so
the features carry genuine, learnable signal (the conservative default model
reaches ROC-AUC ~0.73 on a held-out split), while staying noisy enough that the
problem is not trivial — the Bayes-optimal ceiling is well below 1.0 by design,
so a model scoring ~1.0 here would signal a leak or overfitting, not success.

The generative process is intentionally documented because the whole point of
the project is explainability: we know the ground-truth drivers of risk and
can check that the trained model's SHAP attributions agree with them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import LOAN_PURPOSES, REGIONS

# Ground-truth log-odds weights for the latent default process. These are the
# "true" drivers the model is expected to recover.
_PURPOSE_RISK = {
    "working_capital": 0.0,
    "inventory": 0.1,
    "equipment": -0.1,
    "education": -0.2,
    "home_improvement": -0.1,
    "emergency": 0.6,
}
_REGION_RISK = {
    "andina": 0.0,
    "caribe": 0.15,
    "pacifica": 0.2,
    "orinoquia": 0.1,
    "amazonia": 0.25,
}


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def make_dataset(n: int = 20_000, seed: int = 42) -> pd.DataFrame:
    """Return a DataFrame of ``n`` synthetic applicants with a ``default`` label."""
    rng = np.random.default_rng(seed)

    age = rng.integers(18, 75, size=n)
    # Income in COP (monthly), lognormal, floored at the legal minimum wage band.
    monthly_income = np.clip(rng.lognormal(mean=14.3, sigma=0.55, size=n), 1_000_000, 60_000_000)
    employment_length_years = np.clip(rng.gamma(shape=2.0, scale=2.5, size=n), 0, 40)

    loan_term_months = rng.choice([6, 12, 18, 24, 36, 48, 60], size=n)
    # Loan amount scales with income but with heavy spread.
    loan_amount = np.clip(monthly_income * rng.uniform(0.5, 8.0, size=n), 500_000, 300_000_000)

    num_existing_loans = rng.poisson(lam=1.1, size=n)
    num_late_payments_12m = rng.poisson(lam=0.4, size=n)
    has_collateral = rng.binomial(1, 0.35, size=n)

    # Debt-to-income: existing obligations plus the new installment over income.
    monthly_installment = loan_amount / loan_term_months
    existing_debt_payment = num_existing_loans * monthly_income * rng.uniform(0.03, 0.12, size=n)
    debt_to_income = np.clip(
        (monthly_installment + existing_debt_payment) / monthly_income, 0.0, 3.0
    )

    region = rng.choice(REGIONS, size=n)
    loan_purpose = rng.choice(LOAN_PURPOSES, size=n)

    region_effect = np.array([_REGION_RISK[r] for r in region])
    purpose_effect = np.array([_PURPOSE_RISK[p] for p in loan_purpose])

    # Latent log-odds of default (the ground truth we want the model to learn).
    z = (
        -2.6
        + 2.4 * debt_to_income
        + 0.85 * num_late_payments_12m
        + 0.18 * num_existing_loans
        - 0.05 * employment_length_years
        - 0.45 * has_collateral
        - 0.012 * (age - 18)
        + region_effect
        + purpose_effect
        + rng.normal(0, 0.35, size=n)
    )
    p_default = _sigmoid(z)
    default = rng.binomial(1, p_default)

    frame = pd.DataFrame(
        {
            "age": age.astype(int),
            "monthly_income": monthly_income.round(0),
            "loan_amount": loan_amount.round(0),
            "loan_term_months": loan_term_months.astype(int),
            "employment_length_years": employment_length_years.round(2),
            "debt_to_income": debt_to_income.round(4),
            "num_existing_loans": num_existing_loans.astype(int),
            "num_late_payments_12m": num_late_payments_12m.astype(int),
            "has_collateral": has_collateral.astype(int),
            "region": region,
            "loan_purpose": loan_purpose,
            "default": default.astype(int),
        }
    )
    return frame


def _to_native(value):
    """Cast a numpy scalar to a native Python type for clean JSON serialisation."""
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def sample_applicant(seed: int = 7) -> dict:
    """Return one applicant as a plain dict (no label), for demos and docs."""
    row = make_dataset(n=1, seed=seed).iloc[0].drop(labels=["default"]).to_dict()
    return {k: _to_native(v) for k, v in row.items()}
