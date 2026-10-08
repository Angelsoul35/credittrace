"""Dependency wiring for the API.

Builds a single :class:`ScoringService` from settings: loads the trained model,
opens the database, and — when anchoring is enabled and a contract address plus
signing key are configured — connects a :class:`Web3AnchorClient` to the RPC
endpoint. Tests override :func:`get_service` with a service built on an
in-memory EVM and a temporary database.
"""

from __future__ import annotations

import logging

from app.chain.registry import Web3AnchorClient
from app.config import Settings, get_settings
from app.db.session import init_engine
from app.ml.model import CreditRiskModel
from app.service import RiskPolicy, ScoringService

logger = logging.getLogger("credittrace")

_service: ScoringService | None = None


def build_service(settings: Settings | None = None) -> ScoringService:
    settings = settings or get_settings()
    session_factory = init_engine(settings.database_url)
    model = CreditRiskModel.load(settings.model_dir, settings.model_version or None)

    anchor_client = None
    if settings.chain_enabled:
        if settings.contract_address and settings.chain_private_key:
            from web3 import Web3

            w3 = Web3(Web3.HTTPProvider(settings.chain_rpc_url))
            account = w3.eth.account.from_key(settings.chain_private_key).address
            anchor_client = Web3AnchorClient(
                w3, settings.contract_address, account, settings.chain_private_key
            )
            logger.info("Anchoring enabled against %s", settings.contract_address)
        else:
            logger.warning(
                "CT_CHAIN_ENABLED is true but contract address / key are missing; "
                "decisions will be scored and stored without anchoring."
            )

    policy = RiskPolicy(settings.band_low_max_bps, settings.band_medium_max_bps)
    return ScoringService(model, session_factory, anchor_client, policy)


def get_service() -> ScoringService:
    global _service
    if _service is None:
        _service = build_service()
    return _service


def reset_service() -> None:
    """Clear the cached service (used by tests)."""
    global _service
    _service = None
