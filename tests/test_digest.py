"""Digest determinism and tamper-sensitivity."""

from __future__ import annotations

from app.chain.digest import compute_digest


def _features() -> dict:
    return {"age": 30, "debt_to_income": 0.4, "region": "andina", "has_collateral": 1}


def test_digest_is_32_bytes():
    digest = compute_digest(_features(), "m_abc", 1200, "approve")
    assert isinstance(digest, bytes)
    assert len(digest) == 32


def test_digest_is_deterministic():
    a = compute_digest(_features(), "m_abc", 1200, "approve")
    b = compute_digest(_features(), "m_abc", 1200, "approve")
    assert a == b


def test_digest_independent_of_key_order():
    f1 = {"age": 30, "region": "andina"}
    f2 = {"region": "andina", "age": 30}
    assert compute_digest(f1, "m_abc", 1200, "approve") == compute_digest(
        f2, "m_abc", 1200, "approve"
    )


def test_digest_changes_with_any_field():
    base = compute_digest(_features(), "m_abc", 1200, "approve")
    assert compute_digest({**_features(), "age": 31}, "m_abc", 1200, "approve") != base
    assert compute_digest(_features(), "m_xyz", 1200, "approve") != base
    assert compute_digest(_features(), "m_abc", 1201, "approve") != base
    assert compute_digest(_features(), "m_abc", 1200, "decline") != base
