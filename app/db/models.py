"""ORM models: the persisted record of every credit decision."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Decision(Base):
    """A single scored (and optionally anchored) credit decision.

    The row stores everything needed to reconstruct the on-chain digest, so a
    decision can be independently re-verified long after it was made.
    """

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    applicant: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    score_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[str] = mapped_column(String(16), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Content address of the decision: the same inputs legitimately repeat, so
    # it is indexed for lookup but intentionally NOT unique.
    digest_hex: Mapped[str] = mapped_column(String(66), index=True, nullable=False)
    anchored: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anchor_tx: Mapped[str | None] = mapped_column(String(66), nullable=True)
    anchor_block: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_address: Mapped[str | None] = mapped_column(String(42), nullable=True)

    def to_dict(self) -> dict:
        return {
            "decision_id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "applicant": self.applicant,
            "model_version": self.model_version,
            "probability": self.probability,
            "score_bps": self.score_bps,
            "band": self.band,
            "decision": self.decision,
            "reasons": self.reasons,
            "digest": self.digest_hex,
            "anchor": {
                "anchored": self.anchored,
                "tx_hash": self.anchor_tx,
                "block_number": self.anchor_block,
                "contract_address": self.contract_address,
            },
        }
