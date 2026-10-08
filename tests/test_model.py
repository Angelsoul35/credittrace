"""Model training, scoring and explanation behaviour."""

from __future__ import annotations

import pytest

from app.ml.features import FEATURE_ORDER
from app.ml.model import CreditRiskModel, latest_version


def test_training_produces_versioned_model_with_signal(model: CreditRiskModel):
    assert model.version and model.version.startswith("m_")
    assert model.metadata["metrics"]["roc_auc"] > 0.7


def test_predict_proba_is_a_probability(model: CreditRiskModel, applicant: dict):
    p = model.predict_proba(applicant)
    assert 0.0 <= p <= 1.0


def test_explain_returns_ranked_valid_reasons(model: CreditRiskModel, applicant: dict):
    reasons = model.explain(applicant, top_k=5)
    assert 1 <= len(reasons) <= 5
    magnitudes = [abs(r.contribution) for r in reasons]
    assert magnitudes == sorted(magnitudes, reverse=True)
    for r in reasons:
        assert r.feature in FEATURE_ORDER
        assert r.direction in {"increases_risk", "decreases_risk"}


def test_missing_feature_raises(model: CreditRiskModel, applicant: dict):
    broken = dict(applicant)
    del broken["age"]
    with pytest.raises(ValueError):
        model.predict_proba(broken)


def test_save_and_load_roundtrip(model: CreditRiskModel, applicant: dict, tmp_path):
    path = model.save(tmp_path)
    assert path.exists()
    reloaded = CreditRiskModel.load(tmp_path, model.version)
    assert reloaded.version == model.version
    assert reloaded.predict_proba(applicant) == pytest.approx(model.predict_proba(applicant))
    assert latest_version(tmp_path) == model.version


def test_higher_risk_profile_scores_higher(model: CreditRiskModel, applicant: dict):
    safe = {**applicant, "debt_to_income": 0.1, "num_late_payments_12m": 0, "has_collateral": 1}
    risky = {**applicant, "debt_to_income": 1.2, "num_late_payments_12m": 5, "has_collateral": 0}
    assert model.predict_proba(risky) > model.predict_proba(safe)
