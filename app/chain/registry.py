"""Anchor clients: a Web3-backed client and an in-memory fake.

Both implement :class:`AnchorClient`, so the scoring service depends only on
the interface. The in-memory client mirrors the contract's semantics exactly
(single-use digests, revert-on-duplicate), which lets the service and API be
tested without any EVM, while :class:`Web3AnchorClient` exercises the real
compiled contract against Anvil or an in-memory PyEVM node.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from web3 import Web3
from web3.contract import Contract

from .artifacts import contract_abi, contract_bytecode


class AlreadyAnchoredError(Exception):
    """Raised when a digest has already been anchored (mirrors the contract)."""


@dataclass(frozen=True)
class AnchorReceipt:
    digest_hex: str
    tx_hash: str | None
    block_number: int
    already_anchored: bool


@dataclass(frozen=True)
class AnchorRecord:
    anchored: bool
    submitter: str | None
    timestamp: int
    block_number: int


@runtime_checkable
class AnchorClient(Protocol):
    @property
    def address(self) -> str: ...

    def is_anchored(self, digest: bytes) -> bool: ...

    def record_of(self, digest: bytes) -> AnchorRecord: ...

    def anchor(self, digest: bytes) -> AnchorReceipt: ...


# --------------------------------------------------------------------------- #
# In-memory client
# --------------------------------------------------------------------------- #
class InMemoryAnchorClient:
    """A dict-backed anchor store that mirrors the contract's behaviour."""

    def __init__(self, submitter: str = "0x0000000000000000000000000000000000000001") -> None:
        self._submitter = Web3.to_checksum_address(submitter)
        self._store: dict[bytes, AnchorRecord] = {}
        self._clock = 1

    @property
    def address(self) -> str:
        return "0x0000000000000000000000000000000000000000"

    def is_anchored(self, digest: bytes) -> bool:
        return digest in self._store

    def record_of(self, digest: bytes) -> AnchorRecord:
        return self._store.get(
            digest, AnchorRecord(anchored=False, submitter=None, timestamp=0, block_number=0)
        )

    def anchor(self, digest: bytes) -> AnchorReceipt:
        if digest == bytes(32):
            raise ValueError("digest must be non-zero")
        if digest in self._store:
            raise AlreadyAnchoredError(digest.hex())
        self._clock += 1
        self._store[digest] = AnchorRecord(
            anchored=True,
            submitter=self._submitter,
            timestamp=1_700_000_000 + self._clock,
            block_number=self._clock,
        )
        return AnchorReceipt(
            digest_hex="0x" + digest.hex(),
            tx_hash=None,
            block_number=self._clock,
            already_anchored=False,
        )


# --------------------------------------------------------------------------- #
# Web3 client
# --------------------------------------------------------------------------- #
def deploy_registry(w3: Web3, deployer: str, private_key: str | None = None) -> str:
    """Deploy ``DecisionRegistry`` and return its address."""
    deployer = Web3.to_checksum_address(deployer)
    factory = w3.eth.contract(abi=contract_abi(), bytecode=contract_bytecode())
    if private_key:
        tx = factory.constructor().build_transaction(
            {"from": deployer, "nonce": w3.eth.get_transaction_count(deployer)}
        )
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    else:
        tx_hash = factory.constructor().transact({"from": deployer})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt["contractAddress"]


class Web3AnchorClient:
    """Anchor client backed by a deployed ``DecisionRegistry`` contract."""

    def __init__(
        self,
        w3: Web3,
        contract_address: str,
        account: str,
        private_key: str | None = None,
    ) -> None:
        self._w3 = w3
        self._account = Web3.to_checksum_address(account)
        self._private_key = private_key
        self._contract: Contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=contract_abi()
        )

    @property
    def address(self) -> str:
        return self._contract.address

    def is_anchored(self, digest: bytes) -> bool:
        return bool(self._contract.functions.isAnchored(digest).call())

    def record_of(self, digest: bytes) -> AnchorRecord:
        submitter, timestamp, block_number = self._contract.functions.recordOf(digest).call()
        anchored = int(timestamp) != 0
        return AnchorRecord(
            anchored=anchored,
            submitter=submitter if anchored else None,
            timestamp=int(timestamp),
            block_number=int(block_number),
        )

    def anchor(self, digest: bytes) -> AnchorReceipt:
        if self.is_anchored(digest):
            raise AlreadyAnchoredError("0x" + digest.hex())
        fn = self._contract.functions.anchor(digest)
        if self._private_key:
            tx = fn.build_transaction(
                {"from": self._account, "nonce": self._w3.eth.get_transaction_count(self._account)}
            )
            signed = self._w3.eth.account.sign_transaction(tx, self._private_key)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        else:
            tx_hash = fn.transact({"from": self._account})
        receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash)
        return AnchorReceipt(
            digest_hex="0x" + digest.hex(),
            tx_hash=receipt["transactionHash"].hex(),
            block_number=int(receipt["blockNumber"]),
            already_anchored=False,
        )
