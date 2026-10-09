"""Real-world benchmark of the credit-risk approach on UCI German Credit.

This trains the same kind of pipeline the production model uses (one-hot encoding
plus gradient-boosted trees, explained with SHAP) on the **real** German Credit
data, and reports whether the model is correctly fit: strong on unseen data and
with its training score close to its test score. Neither underfit (a model that
cannot separate the classes) nor overfit (a model that memorises the training rows
and collapses out of sample) is acceptable.

The chosen hyper-parameters are not a capacity cut: on this data a deep, unregular-
ised model scores *lower* in cross-validation (it memorises), while an over-
regularised one starts losing cross-validated AUC. The reported configuration is the
one that reaches the data's attainable ceiling (~0.78 ROC-AUC, consistent with the
German Credit literature) with the training/test scores closest together.

Run it with ``python -m app.ml.benchmark``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from app.ml.model import _ks_statistic
from app.ml.real_data import TARGET, feature_columns, load_german_credit

# The well-fit configuration (see module docstring and the fit curve in the study
# guide): strongest cross-validated AUC with the train/test gap closed.
_WELL_FIT_PARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 2,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 5.0,
    "min_child_weight": 10,
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "tree_method": "hist",
    "random_state": 42,
}

_SEED = 42
_N_SPLITS = 5


@dataclass
class ModelResult:
    name: str
    cv_auc_mean: float
    cv_auc_std: float
    train_auc: float
    test_auc: float
    gap: float = field(init=False)

    def __post_init__(self) -> None:
        self.gap = round(self.train_auc - self.test_auc, 4)


@dataclass
class BenchmarkReport:
    n_rows: int
    default_rate: float
    n_numeric: int
    n_categorical: int
    xgb: ModelResult
    logistic: ModelResult
    ks: float
    brier: float
    confusion: dict[str, int]
    threshold: float
    shap_drivers: list[tuple[str, float]]

    @property
    def verdict(self) -> str:
        """A plain reading of whether the model is correctly fit."""
        if self.xgb.cv_auc_mean < 0.70:
            return "underfit: cross-validated AUC is below the data's attainable signal"
        if self.xgb.gap > 0.12:
            return "overfit: training AUC runs well ahead of test AUC"
        return "well-fit: strong cross-validated AUC with train and test scores close"


def _xgb_pipeline(numeric: list[str], categorical: list[str], params: dict) -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", "passthrough", numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ]
    )
    return Pipeline([("pre", pre), ("clf", XGBClassifier(**params))])


def _logistic_pipeline(numeric: list[str], categorical: list[str]) -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ]
    )
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=2000))])


def _evaluate(name: str, pipe: Pipeline, X: pd.DataFrame, y: pd.Series) -> ModelResult:
    cv = StratifiedKFold(n_splits=_N_SPLITS, shuffle=True, random_state=_SEED)
    cv_auc = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=_SEED
    )
    pipe.fit(X_train, y_train)
    train_auc = roc_auc_score(y_train, pipe.predict_proba(X_train)[:, 1])
    test_auc = roc_auc_score(y_test, pipe.predict_proba(X_test)[:, 1])
    return ModelResult(
        name=name,
        cv_auc_mean=round(float(cv_auc.mean()), 4),
        cv_auc_std=round(float(cv_auc.std()), 4),
        train_auc=round(float(train_auc), 4),
        test_auc=round(float(test_auc), 4),
    )


def _shap_drivers(
    pipe: Pipeline,
    X_train: pd.DataFrame,
    numeric: list[str],
    categorical: list[str],
    top_k: int = 6,
) -> list[tuple[str, float]]:
    """Global SHAP importance (mean |value|) aggregated back to original features."""
    import shap

    pre = pipe.named_steps["pre"]
    clf = pipe.named_steps["clf"]
    transformed = pre.transform(X_train)
    names = list(pre.get_feature_names_out())
    explainer = shap.TreeExplainer(clf)
    values = np.abs(np.asarray(explainer.shap_values(transformed))).mean(axis=0)

    aggregated: dict[str, float] = {}
    for name, val in zip(names, values, strict=True):
        # ColumnTransformer names look like "num__duration" / "cat__status_... < 0 DM".
        body = name.split("__", 1)[1] if "__" in name else name
        parent = next((c for c in categorical if body.startswith(c + "_")), None)
        key = parent if parent is not None else body  # roll one-hot columns up to the feature
        aggregated[key] = aggregated.get(key, 0.0) + float(val)
    ranked = sorted(aggregated.items(), key=lambda kv: kv[1], reverse=True)
    return [(k, round(v, 4)) for k, v in ranked[:top_k]]


def run_benchmark(threshold: float = 0.5) -> BenchmarkReport:
    df = load_german_credit()
    numeric, categorical = feature_columns(df)
    feats = numeric + categorical
    X, y = df[feats], df[TARGET]

    xgb = _evaluate(
        "XGBoost (well-fit)", _xgb_pipeline(numeric, categorical, _WELL_FIT_PARAMS), X, y
    )
    logistic = _evaluate("Logistic regression", _logistic_pipeline(numeric, categorical), X, y)

    # Held-out metrics and SHAP drivers from the XGBoost model.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=_SEED
    )
    pipe = _xgb_pipeline(numeric, categorical, _WELL_FIT_PARAMS)
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()

    return BenchmarkReport(
        n_rows=int(len(df)),
        default_rate=round(float(y.mean()), 4),
        n_numeric=len(numeric),
        n_categorical=len(categorical),
        xgb=xgb,
        logistic=logistic,
        ks=round(_ks_statistic(y_test.to_numpy(), proba), 4),
        brier=round(float(brier_score_loss(y_test, proba)), 4),
        confusion={"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        threshold=threshold,
        shap_drivers=_shap_drivers(pipe, X_train, numeric, categorical),
    )


def format_report(r: BenchmarkReport) -> str:
    lines = [
        "CreditTrace — real-world benchmark (UCI Statlog German Credit)",
        "=" * 62,
        f"rows: {r.n_rows}   default rate: {r.default_rate:.1%}   "
        f"features: {r.n_numeric} numeric + {r.n_categorical} categorical",
        "",
        f"{'model':<22} {'CV ROC-AUC':<16} {'train':>7} {'test':>7} {'gap':>7}",
    ]
    for m in (r.xgb, r.logistic):
        lines.append(
            f"{m.name:<22} {m.cv_auc_mean:.3f} +/- {m.cv_auc_std:.3f}   "
            f"{m.train_auc:>7.3f} {m.test_auc:>7.3f} {m.gap:>7.3f}"
        )
    lines += [
        "",
        f"XGBoost held-out: KS={r.ks:.3f}  Brier={r.brier:.3f}  "
        f"confusion@{r.threshold:.2f} (tn,fp,fn,tp)="
        f"({r.confusion['tn']},{r.confusion['fp']},{r.confusion['fn']},{r.confusion['tp']})",
        "",
        "top SHAP risk drivers (global mean |contribution|):",
    ]
    lines += [f"  {name:<28} {val:.4f}" for name, val in r.shap_drivers]
    lines += ["", f"verdict: {r.verdict}"]
    return "\n".join(lines)


def main() -> None:
    print(format_report(run_benchmark()))


if __name__ == "__main__":  # pragma: no cover
    main()
