"""Contract interaction: anchoring, lookups, access control, in-memory parity."""

from __future__ import annotations

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.exceptions import ContractLogicError

from app.chain.digest import compute_digest
from app.chain.registry import (
    AlreadyAnchoredError,
    InMemoryAnchorClient,
    Web3AnchorClient,
    deploy_registry,
)

# A revert surfaces as web3's ContractLogicError against a real node (Anvil) and
# as eth-tester's TransactionFailed against the in-memory backend used here.
REVERT_ERRORS = (ContractLogicError, TransactionFailed)

pytestmark = pytest.mark.chain


def _digest(tag: str) -> bytes:
    return compute_digest({"tag": tag}, "m_test", 1000, "review")


def test_anchor_and_lookup(anchor_client: Web3AnchorClient):
    digest = _digest("a")
    assert anchor_client.is_anchored(digest) is False
    receipt = anchor_client.anchor(digest)
    assert receipt.block_number > 0
    assert receipt.tx_hash is not None
    assert anchor_client.is_anchored(digest) is True

    record = anchor_client.record_of(digest)
    assert record.anchored is True
    assert record.timestamp > 0
    assert Web3.is_address(record.submitter)


def test_duplicate_anchor_is_rejected(anchor_client: Web3AnchorClient):
    digest = _digest("b")
    anchor_client.anchor(digest)
    with pytest.raises(AlreadyAnchoredError):
        anchor_client.anchor(digest)


def test_access_control_blocks_non_scorer(w3):
    owner, outsider = w3.eth.accounts[0], w3.eth.accounts[1]
    address = deploy_registry(w3, owner)
    rogue = Web3AnchorClient(w3, address, outsider)
    with pytest.raises(REVERT_ERRORS):  # contract reverts with NotScorer()
        rogue.anchor(_digest("c"))


def test_in_memory_client_matches_contract_semantics():
    client = InMemoryAnchorClient()
    digest = _digest("d")
    assert client.is_anchored(digest) is False
    client.anchor(digest)
    assert client.is_anchored(digest) is True
    assert client.record_of(digest).anchored is True
    with pytest.raises(AlreadyAnchoredError):
        client.anchor(digest)
