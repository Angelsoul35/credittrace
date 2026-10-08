"""Deploy ``DecisionRegistry`` to the configured JSON-RPC endpoint.

Prints the deployed contract address to stdout so a shell can capture it::

    export CT_CONTRACT_ADDRESS="$(python -m scripts.deploy_local)"

Used by the Docker entrypoint to wire the API to a fresh Anvil chain.
"""

from __future__ import annotations

import sys

from web3 import Web3

from app.chain.registry import deploy_registry
from app.config import get_settings


def main() -> None:
    settings = get_settings()
    w3 = Web3(Web3.HTTPProvider(settings.chain_rpc_url))
    if not w3.is_connected():
        print(f"Cannot connect to RPC at {settings.chain_rpc_url}", file=sys.stderr)
        sys.exit(1)

    if settings.chain_private_key:
        account = w3.eth.account.from_key(settings.chain_private_key).address
        address = deploy_registry(w3, account, settings.chain_private_key)
    else:
        account = w3.eth.accounts[0]
        address = deploy_registry(w3, account)

    print(address)


if __name__ == "__main__":
    main()
