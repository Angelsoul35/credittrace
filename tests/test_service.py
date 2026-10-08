"""End-to-end service behaviour: score, persist, anchor, verify, tamper."""

from __future__ import annotations

from app.service import ScoringService


def test_score_persists_and_anchors(service: ScoringService, applicant: dict):
    result = service.score(applicant)
    assert result["decision"] in {"approve", "review", "decline"}
    assert result["band"] in {"low", "medium", "high"}
    assert 0 <= result["score_bps"] <= 10_000
    assert result["anchor"]["enabled"] is True
    assert result["anchor"]["anchored"] is True
    assert result["anchor"]["digest"].startswith("0x")

    stored = service.get(result["decision_id"])
    assert stored is not None
    assert stored["digest"] == result["anchor"]["digest"]


def test_verify_confirms_untampered_decision(service: ScoringService, applicant: dict):
    result = service.score(applicant)
    verdict = service.verify(result["decision_id"])
    assert verdict["digest_matches"] is True
    assert verdict["on_chain"]["anchored"] is True
    assert verdict["status"] == "verified"


def test_verify_detects_tampering(service: ScoringService, applicant: dict):
    from app.db.models import Decision

    result = service.score(applicant)
    with service.session_factory() as db:
        row = db.get(Decision, result["decision_id"])
        row.score_bps = row.score_bps + 1  # tamper with a stored field
        db.add(row)
        db.commit()

    verdict = service.verify(result["decision_id"])
    assert verdict["digest_matches"] is False
    assert verdict["status"] == "digest_mismatch"


def test_identical_applicant_is_idempotent_on_chain(service: ScoringService, applicant: dict):
    first = service.score(applicant)
    second = service.score(applicant)
    assert first["anchor"]["digest"] == second["anchor"]["digest"]
    assert first["anchor"]["already_anchored"] is False
    assert second["anchor"]["already_anchored"] is True


def test_anchoring_disabled(model, session_factory, applicant: dict):
    service = ScoringService(model, session_factory, anchor_client=None)
    result = service.score(applicant)
    assert result["anchor"]["enabled"] is False
    assert result["anchor"]["anchored"] is False
    verdict = service.verify(result["decision_id"])
    assert verdict["status"] == "chain_disabled"
    assert verdict["digest_matches"] is True


def test_unknown_decision_returns_none(service: ScoringService):
    assert service.get("does-not-exist") is None
    assert service.verify("does-not-exist") is None
