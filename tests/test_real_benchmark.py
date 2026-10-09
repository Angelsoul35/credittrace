"""Tests for the real-world German Credit benchmark.

These prove three things and fail if any breaks:
1. the vendored data really is the canonical German Credit set (shape + balance);
2. the model is *correctly fit* on real data — strong on unseen folds (not underfit)
   and with its training score close to its test score (not overfit);
3. SHAP recovers the risk drivers the credit literature expects.
"""

from __future__ import annotations

import pytest

from app.ml.benchmark import run_benchmark
from app.ml.real_data import TARGET, feature_columns, load_german_credit


@pytest.fixture(scope="module")
def report():
    # Train once; the benchmark is deterministic (fixed seeds), so every test
    # reads the same report instead of retraining.
    return run_benchmark()


def test_loads_the_real_german_credit_dataset():
    df = load_german_credit()
    # Canonical size and class balance (700 good / 300 bad). A swapped or
    # synthetic file would not match, so this anchors "real data".
    assert df.shape == (1000, 22)  # 20 features + raw target + derived default
    assert int(df[TARGET].sum()) == 300  # 300 bad credits = defaults
    numeric, categorical = feature_columns(df)
    assert len(numeric) == 7
    assert len(categorical) == 13


def test_model_is_well_fit_on_real_data(report):

    # Not underfit: cross-validated AUC is clearly above chance and reaches the
    # data's attainable signal (German Credit tops out around 0.78-0.80).
    assert report.xgb.cv_auc_mean >= 0.72, report.xgb

    # Not a leak / not fake-perfect: real German Credit cannot be separated near 1.0.
    assert report.xgb.cv_auc_mean <= 0.85, report.xgb

    # Not overfit: the training AUC does not run far ahead of the test AUC.
    assert report.xgb.gap <= 0.12, report.xgb

    assert report.verdict.startswith("well-fit")

    # The logistic baseline is competitive here (1,000 rows), which is itself the
    # lesson that more model capacity is not automatically better.
    assert abs(report.xgb.cv_auc_mean - report.logistic.cv_auc_mean) <= 0.05


def test_shap_recovers_known_credit_risk_drivers(report):
    drivers = [name for name, _ in report.shap_drivers]
    # Checking-account status is the dominant predictor in the German Credit
    # literature; it must surface at the very top.
    assert "status" in drivers[:2], drivers
    # The other classic drivers should be present among the top features.
    assert {"duration", "credit_history"} & set(drivers), drivers


def test_format_report_renders_the_measured_numbers(report):
    from app.ml.benchmark import format_report

    text = format_report(report)
    # The rendered report must carry the real figures, not placeholders.
    assert "German Credit" in text
    assert f"{report.xgb.cv_auc_mean:.3f}" in text
    assert "status" in text  # top SHAP driver
    assert report.verdict in text


def test_main_prints_the_report(capsys):
    from app.ml.benchmark import main

    main()
    out = capsys.readouterr().out
    assert "CreditTrace — real-world benchmark" in out
    assert "verdict:" in out


def _report_with(cv_auc: float, train_auc: float, test_auc: float):
    from app.ml.benchmark import BenchmarkReport, ModelResult

    model = ModelResult("x", cv_auc, 0.02, train_auc, test_auc)
    return BenchmarkReport(
        n_rows=1000,
        default_rate=0.3,
        n_numeric=7,
        n_categorical=13,
        xgb=model,
        logistic=model,
        ks=0.4,
        brier=0.16,
        confusion={"tn": 1, "fp": 1, "fn": 1, "tp": 1},
        threshold=0.5,
        shap_drivers=[("status", 0.7)],
    )


def test_verdict_classifies_underfit_overfit_and_well_fit():
    # Below the signal floor -> underfit; wide train/test gap -> overfit; otherwise well-fit.
    assert _report_with(0.65, 0.66, 0.64).verdict.startswith("underfit")
    assert _report_with(0.80, 0.99, 0.80).verdict.startswith("overfit")
    assert _report_with(0.79, 0.85, 0.78).verdict.startswith("well-fit")


def test_loader_rejects_a_missing_or_malformed_file(tmp_path):
    import pandas as pd
    import pytest

    from app.ml.real_data import load_german_credit

    with pytest.raises(FileNotFoundError):
        load_german_credit(tmp_path / "nope.csv")

    wrong_shape = tmp_path / "wrong.csv"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(wrong_shape, index=False)
    with pytest.raises(ValueError, match="canonical German Credit shape"):
        load_german_credit(wrong_shape)

    # Right size, wrong schema (no credit_risk column) -> rejected too.
    no_target = tmp_path / "no_target.csv"
    pd.DataFrame({f"c{i}": range(1000) for i in range(21)}).to_csv(no_target, index=False)
    with pytest.raises(ValueError, match="Missing target"):
        load_german_credit(no_target)


def test_fetch_writes_the_dataset(tmp_path, monkeypatch):
    import app.ml.real_data as rd

    payload = b"credit_risk\n1\n0\n"

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return payload

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResp())
    dest = tmp_path / "german_credit.csv"
    out = rd.fetch(dest)
    assert out == dest
    assert dest.read_bytes() == payload
