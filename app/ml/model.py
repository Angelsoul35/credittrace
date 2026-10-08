"""Credit-risk model: training, scoring and SHAP-based explanations.

The model is a scikit-learn ``Pipeline`` (a ``ColumnTransformer`` for one-hot
encoding plus an ``XGBClassifier``). It is wrapped by :class:`CreditRiskModel`,
which adds three things a raw estimator does not give you but a lending system
needs:

* a **content-addressed version** derived from the hyper-parameters and a
  fingerprint of the training data, so every stored decision can name the exact
  model that produced it;
* **calibrated probabilities and reported metrics** (ROC-AUC, KS, Brier) so the
  score means something;
* **per-decision explanations** via SHAP, aggregated back to the original
  human-readable features (one-hot columns are summed into their parent).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.compose import ColumnTransformer
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from .features import (
    CATEGORICAL_FEATURES,
    FEATURE_LABELS,
    FEATURE_ORDER,
    NUMERIC_FEATURES,
    TARGET,
)

_DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "reg_lambda": 1.0,
    "min_child_weight": 5,
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "tree_method": "hist",
    "random_state": 42,
}

_PIPELINE_FILE = "pipeline.joblib"
_METADATA_FILE = "metadata.json"


@dataclass
class Reason:
    """One explanation line: how a feature pushed this applicant's risk."""

    feature: str
    label: str
    value: Any
    contribution: float  # signed SHAP value in log-odds space
    direction: str = field(init=False)

    def __post_init__(self) -> None:
        self.direction = "increases_risk" if self.contribution > 0 else "decreases_risk"

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "label": self.label,
            "value": self.value,
            "contribution": round(float(self.contribution), 5),
            "direction": self.direction,
        }


@dataclass
class TrainingReport:
    version: str
    trained_at: str
    n_rows: int
    default_rate: float
    metrics: dict[str, float]
    params: dict[str, Any]


def _ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Kolmogorov-Smirnov separation between good and bad distributions."""
    order = np.argsort(y_score)
    y_true = np.asarray(y_true)[order]
    y_score = np.asarray(y_score)[order]
    total_bad = y_true.sum()
    total_good = len(y_true) - total_bad
    if total_bad == 0 or total_good == 0:
        return 0.0
    cum_bad = np.cumsum(y_true) / total_bad
    cum_good = np.cumsum(1 - y_true) / total_good
    return float(np.max(np.abs(cum_bad - cum_good)))


class CreditRiskModel:
    """Trainable, explainable, versioned credit-risk estimator."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params: dict[str, Any] = {**_DEFAULT_PARAMS, **(params or {})}
        self.pipeline: Pipeline | None = None
        self.version: str | None = None
        self.metadata: dict[str, Any] = {}
        self._explainer: shap.TreeExplainer | None = None
        self._transformed_names: list[str] | None = None

    # ------------------------------------------------------------------ build
    def _build_pipeline(self) -> Pipeline:
        preprocess = ColumnTransformer(
            transformers=[
                ("num", "passthrough", NUMERIC_FEATURES),
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    CATEGORICAL_FEATURES,
                ),
            ],
            remainder="drop",
            verbose_feature_names_out=True,
        )
        classifier = XGBClassifier(**self.params)
        return Pipeline([("preprocess", preprocess), ("clf", classifier)])

    @staticmethod
    def _data_fingerprint(df: pd.DataFrame) -> str:
        digest = hashlib.sha256()
        digest.update(str(df.shape).encode())
        digest.update(",".join(map(str, df.columns)).encode())
        # A stable hash of the content without depending on pandas' hashing.
        digest.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
        return digest.hexdigest()

    def _compute_version(self, data_fingerprint: str) -> str:
        payload = json.dumps(
            {"params": self.params, "data": data_fingerprint, "features": FEATURE_ORDER},
            sort_keys=True,
        )
        return "m_" + hashlib.sha256(payload.encode()).hexdigest()[:12]

    # ------------------------------------------------------------------ train
    def train(self, df: pd.DataFrame, test_size: float = 0.25) -> TrainingReport:
        X = df[FEATURE_ORDER]
        y = df[TARGET].astype(int)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.params["random_state"], stratify=y
        )

        self.pipeline = self._build_pipeline()
        self.pipeline.fit(X_train, y_train)

        proba = self.pipeline.predict_proba(X_test)[:, 1]
        metrics = {
            "roc_auc": float(roc_auc_score(y_test, proba)),
            "ks": _ks_statistic(y_test.to_numpy(), proba),
            "brier": float(brier_score_loss(y_test, proba)),
        }

        self.version = self._compute_version(self._data_fingerprint(df))
        self.metadata = {
            "version": self.version,
            "trained_at": datetime.now(UTC).isoformat(),
            "n_rows": int(len(df)),
            "default_rate": round(float(y.mean()), 4),
            "metrics": {k: round(v, 4) for k, v in metrics.items()},
            "params": self.params,
            "feature_order": FEATURE_ORDER,
        }
        self._init_explainer()
        return TrainingReport(
            version=self.version,
            trained_at=self.metadata["trained_at"],
            n_rows=self.metadata["n_rows"],
            default_rate=self.metadata["default_rate"],
            metrics=self.metadata["metrics"],
            params=self.params,
        )

    # --------------------------------------------------------------- explain
    def _init_explainer(self) -> None:
        assert self.pipeline is not None
        preprocess = self.pipeline.named_steps["preprocess"]
        clf = self.pipeline.named_steps["clf"]
        self._transformed_names = list(preprocess.get_feature_names_out())
        self._explainer = shap.TreeExplainer(clf)

    def _as_frame(self, record: dict[str, Any]) -> pd.DataFrame:
        missing = [f for f in FEATURE_ORDER if f not in record]
        if missing:
            raise ValueError(f"Missing features: {missing}")
        return pd.DataFrame([{f: record[f] for f in FEATURE_ORDER}])

    def predict_proba(self, record: dict[str, Any]) -> float:
        if self.pipeline is None:
            raise RuntimeError("Model is not trained or loaded.")
        return float(self.pipeline.predict_proba(self._as_frame(record))[0, 1])

    def explain(self, record: dict[str, Any], top_k: int = 5) -> list[Reason]:
        """Return the ``top_k`` features that most moved this applicant's risk.

        SHAP values are computed on the one-hot-encoded matrix and then summed
        back to the original feature (every ``region_*`` column rolls up into
        ``region``), so the credit officer sees real features, not encodings.
        """
        if self.pipeline is None or self._explainer is None:
            raise RuntimeError("Model is not trained or loaded.")

        frame = self._as_frame(record)
        preprocess = self.pipeline.named_steps["preprocess"]
        transformed = preprocess.transform(frame)
        shap_values = self._explainer.shap_values(transformed)
        contributions = np.asarray(shap_values)[0]

        aggregated: dict[str, float] = dict.fromkeys(FEATURE_ORDER, 0.0)
        for name, value in zip(self._transformed_names or [], contributions, strict=True):
            # ColumnTransformer prefixes names as "num__age" / "cat__region_caribe".
            body = name.split("__", 1)[1] if "__" in name else name
            parent = next((f for f in CATEGORICAL_FEATURES if body.startswith(f + "_")), None)
            key = parent if parent is not None else body
            if key in aggregated:
                aggregated[key] += float(value)

        reasons = [
            Reason(feature=f, label=FEATURE_LABELS[f], value=record[f], contribution=c)
            for f, c in aggregated.items()
        ]
        reasons.sort(key=lambda r: abs(r.contribution), reverse=True)
        return reasons[:top_k]

    # ------------------------------------------------------------- persistence
    def save(self, model_dir: str | Path) -> Path:
        if self.pipeline is None or self.version is None:
            raise RuntimeError("Nothing to save: train the model first.")
        target = Path(model_dir) / self.version
        target.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, target / _PIPELINE_FILE)
        (target / _METADATA_FILE).write_text(json.dumps(self.metadata, indent=2))
        return target

    @classmethod
    def load(cls, model_dir: str | Path, version: str | None = None) -> CreditRiskModel:
        base = Path(model_dir)
        resolved = version or latest_version(base)
        if resolved is None:
            raise FileNotFoundError(f"No trained model found under {base!s}")
        path = base / resolved
        model = cls()
        model.pipeline = joblib.load(path / _PIPELINE_FILE)
        model.metadata = json.loads((path / _METADATA_FILE).read_text())
        model.version = model.metadata["version"]
        model.params = model.metadata.get("params", model.params)
        model._init_explainer()
        return model


def latest_version(model_dir: str | Path) -> str | None:
    """Return the most recently trained model version in ``model_dir``."""
    base = Path(model_dir)
    if not base.exists():
        return None
    candidates = [p for p in base.iterdir() if p.is_dir() and (p / _METADATA_FILE).exists()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: json.loads((p / _METADATA_FILE).read_text())["trained_at"])
    return candidates[-1].name
