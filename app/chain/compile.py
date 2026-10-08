"""Compile ``DecisionRegistry.sol`` into the committed ABI + bytecode artifact.

Compilation is delegated to the pinned ``solc-js`` compiler under
``contracts/`` (``node contracts/compile.js``). That keeps a single, portable
compilation path that needs no native toolchain and runs identically in local
development and in CI. The resulting ``contracts/artifacts/DecisionRegistry.json``
is committed, so neither the runtime service nor the test-suite needs a
compiler: they load the artifact and deploy it to any JSON-RPC endpoint.

Run with ``python -m app.chain.compile`` (or ``make compile``).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
ARTIFACT_PATH = CONTRACTS_DIR / "artifacts" / "DecisionRegistry.json"


def compile_contract() -> Path:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if npm is None or node is None:
        raise RuntimeError("Node.js and npm are required to compile the contract.")
    if not (CONTRACTS_DIR / "node_modules" / "solc").exists():
        subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=CONTRACTS_DIR, check=True)
    subprocess.run([node, "compile.js"], cwd=CONTRACTS_DIR, check=True)
    return ARTIFACT_PATH


if __name__ == "__main__":
    try:
        path = compile_contract()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Compilation failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Artifact at {path}")
