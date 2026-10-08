"""The scoring service: score an applicant, persist the decision, anchor it.

This is the orchestration layer the API is a thin shell over. It depends on the
model and an :class:`AnchorClient` through their interfaces, so it can run with
a real contract, with the in-memory fake, or with anchoring switched off.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.chain.digest import compute_digest, to_hex
from app.chain.registry import AlreadyAnchoredError, AnchorClient
from app.db.models import Decision
from app.ml.features import FEATURE_ORDER
from app.ml.model import CreditRiskModel


@dataclass
class RiskPolicy:
    """Maps a probability of default (in bps) to a band and an action."""

    band_low_max_bps: int = 1500
    band_medium_max_bps: int = 4000

    def classify(self, score_bps: int) -> tuple[str, str]:
        if score_bps <= self.band_low_max_bps:
            return "low", "approve"
        if score_bps <= self.band_medium_max_bps:
            return "medium", "review"
        return "high", "decline"


class ScoringService:
    def __init__(
        self,
        model: CreditRiskModel,
        session_factory: sessionmaker[Session],
        anchor_client: AnchorClient | None = None,
        policy: RiskPolicy | None = None,
    ) -> None:
        self.model = model
        self.session_factory = session_factory
        self.anchor_client = anchor_client
        self.policy = policy or RiskPolicy()

    def _canonical_features(self, applicant: dict) -> dict:
        return {k: applicant[k] for k in FEATURE_ORDER}

    def score(self, applicant: dict) -> dict:
        features = self._canonical_features(applicant)
        probability = self.model.predict_proba(features)
        score_bps = int(round(probability * 10_000))
        band, decision = self.policy.classify(score_bps)
        reasons = [r.as_dict() for r in self.model.explain(features)]

        assert self.model.version is not None
        digest = compute_digest(features, self.model.version, score_bps, decision)
        digest_hex = to_hex(digest)
        decision_id = str(uuid.uuid4())

        anchored = False
        tx_hash: str | None = None
        block_number: int | None = None
        already = False
        contract_address: str | None = None

        if self.anchor_client is not None:
            contract_address = self.anchor_client.address
            if self.anchor_client.is_anchored(digest):
                anchored, already = True, True
                record = self.anchor_client.record_of(digest)
                block_number = record.block_number
            else:
                try:
                    receipt = self.anchor_client.anchor(digest)
                    anchored = True
                    tx_hash = receipt.tx_hash
                    block_number = receipt.block_number
                except AlreadyAnchoredError:
                    anchored, already = True, True

        row = Decision(
            id=decision_id,
            applicant=features,
            model_version=self.model.version,
            probability=probability,
            score_bps=score_bps,
            band=band,
            decision=decision,
            reasons=reasons,
            digest_hex=digest_hex,
            anchored=anchored,
            anchor_tx=tx_hash,
            anchor_block=block_number,
            contract_address=contract_address,
        )
        with self.session_factory() as db:
            db.add(row)
            db.commit()

        return {
            "decision_id": decision_id,
            "model_version": self.model.version,
            "probability": probability,
            "score_bps": score_bps,
            "band": band,
            "decision": decision,
            "reasons": reasons,
            "anchor": {
                "enabled": self.anchor_client is not None,
                "anchored": anchored,
                "digest": digest_hex,
                "tx_hash": tx_hash,
                "block_number": block_number,
                "contract_address": contract_address,
                "already_anchored": already,
            },
        }

    def get(self, decision_id: str) -> dict | None:
        with self.session_factory() as db:
            row = db.get(Decision, decision_id)
            return row.to_dict() if row else None

    def verify(self, decision_id: str) -> dict | None:
        """Recompute the digest from stored fields and check it against the chain."""
        with self.session_factory() as db:
            row = db.get(Decision, decision_id)
            if row is None:
                return None

            recomputed = compute_digest(
                row.applicant, row.model_version, row.score_bps, row.decision
            )
            recomputed_hex = to_hex(recomputed)
            digest_matches = recomputed_hex == row.digest_hex

            on_chain = {
                "anchored": False,
                "submitter": None,
                "timestamp": 0,
                "block_number": 0,
                "contract_address": row.contract_address,
            }
            if self.anchor_client is None:
                status = "chain_disabled"
            else:
                record = self.anchor_client.record_of(recomputed)
                on_chain.update(
                    anchored=record.anchored,
                    submitter=record.submitter,
                    timestamp=record.timestamp,
                    block_number=record.block_number,
                    contract_address=self.anchor_client.address,
                )
                if not digest_matches:
                    status = "digest_mismatch"
                elif record.anchored:
                    status = "verified"
                else:
                    status = "not_anchored"

            return {
                "decision_id": decision_id,
                "stored_digest": row.digest_hex,
                "recomputed_digest": recomputed_hex,
                "digest_matches": digest_matches,
                "on_chain": on_chain,
                "status": status,
            }
