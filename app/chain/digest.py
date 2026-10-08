"""Canonical decision payload and its keccak256 digest.

The on-chain registry stores only a 32-byte digest, never applicant data.
The digest binds together everything that makes a decision reproducible:

* the exact feature values that were scored,
* the model version that scored them,
* the resulting probability of default (in basis points), and
* the policy outcome (approve / review / decline).

Because the serialisation is canonical (sorted keys, no insignificant
whitespace), the same decision always produces the same digest, and any change
to any field produces a different one. That is what makes the anchor
*tamper-evident*: a holder of the original payload can recompute the digest and
check it against the chain.
"""

from __future__ import annotations

import json
from typing import Any

from eth_utils import keccak


def canonical_payload(
    features: dict[str, Any],
    model_version: str,
    score_bps: int,
    decision: str,
) -> bytes:
    """Serialise a decision deterministically to UTF-8 bytes."""
    obj = {
        "decision": decision,
        "features": features,
        "model_version": model_version,
        "score_bps": int(score_bps),
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_digest(
    features: dict[str, Any],
    model_version: str,
    score_bps: int,
    decision: str,
) -> bytes:
    """Return the 32-byte keccak256 digest of the canonical payload."""
    return keccak(canonical_payload(features, model_version, score_bps, decision))


def to_hex(digest: bytes) -> str:
    return "0x" + digest.hex()
