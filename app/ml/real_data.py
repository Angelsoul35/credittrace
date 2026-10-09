"""Load the real UCI Statlog *German Credit* dataset.

This is the real-world counterpart to the synthetic generator in :mod:`app.ml.data`.
The synthetic set exists to validate the explainability story (we know its ground-truth
risk drivers and can check SHAP recovers them); this real set exists to show the same
modelling approach works on real applicants, where the attainable ROC-AUC is ~0.74-0.80
(literature-consistent), not a suspicious 1.0.

The CSV is **vendored** under ``datasets/`` (see ``datasets/README.md`` for full
provenance) so training and tests are deterministic and run offline. ``fetch()``
re-downloads it from the public GitHub mirror when needed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATASET_PATH = _REPO_ROOT / "datasets" / "german_credit.csv"
_SOURCE_URL = "https://raw.githubusercontent.com/selva86/datasets/master/GermanCredit.csv"

_RAW_TARGET = "credit_risk"  # 1 = good, 0 = bad (this mirror's recoding)
TARGET = "default"  # 1 = bad credit / default = the event we predict
EXPECTED_SHAPE = (1000, 21)  # the canonical German Credit size (20 features + target)

# Human-readable labels for turning model attributions into reasons a credit
# officer understands (the same role FEATURE_LABELS plays for the synthetic model).
FEATURE_LABELS: dict[str, str] = {
    "status": "Checking-account status",
    "duration": "Credit duration (months)",
    "credit_history": "Credit history",
    "purpose": "Loan purpose",
    "amount": "Credit amount (DM)",
    "savings": "Savings-account balance",
    "employment_duration": "Employment duration",
    "installment_rate": "Installment rate (% of income)",
    "personal_status_sex": "Personal status and sex",
    "other_debtors": "Other debtors / guarantors",
    "present_residence": "Years at present residence",
    "property": "Property owned",
    "age": "Age (years)",
    "other_installment_plans": "Other installment plans",
    "housing": "Housing",
    "number_credits": "Number of existing credits",
    "job": "Job qualification",
    "people_liable": "Dependents",
    "telephone": "Registered telephone",
    "foreign_worker": "Foreign worker",
}


def fetch(dest: Path | None = None) -> Path:
    """Download the dataset from the public mirror into ``datasets/``.

    Only needed to refresh the vendored copy; normal use reads the committed file.
    """
    import urllib.request

    target = dest or _DATASET_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(_SOURCE_URL, timeout=30) as resp:  # noqa: S310 - fixed HTTPS URL
        target.write_bytes(resp.read())
    return target


def load_german_credit(path: str | Path | None = None) -> pd.DataFrame:
    """Return the German Credit data with a derived ``default`` column.

    Raises if the vendored file is missing or does not have the canonical shape,
    so a corrupted or swapped dataset fails loudly instead of silently training
    on the wrong data.
    """
    p = Path(path) if path is not None else _DATASET_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"German Credit CSV not found at {p}. Run "
            "`python -c 'from app.ml.real_data import fetch; fetch()'` to download it."
        )
    df = pd.read_csv(p)
    if df.shape != EXPECTED_SHAPE:
        raise ValueError(
            f"Expected the canonical German Credit shape {EXPECTED_SHAPE}, got {df.shape}. "
            "The vendored file looks wrong."
        )
    if _RAW_TARGET not in df.columns:
        raise ValueError(f"Missing target column {_RAW_TARGET!r}.")
    df[TARGET] = (df[_RAW_TARGET] == 0).astype(int)
    return df


def feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Split the feature columns into (numeric, categorical), excluding the targets."""
    feats = [c for c in df.columns if c not in (_RAW_TARGET, TARGET)]
    numeric = [c for c in feats if is_numeric_dtype(df[c])]
    categorical = [c for c in feats if not is_numeric_dtype(df[c])]
    return numeric, categorical
