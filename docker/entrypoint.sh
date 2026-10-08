#!/usr/bin/env bash
# Bring up the API against a fresh Anvil chain: wait for RPC, train a model if
# none is present, deploy the registry if no address was provided, then serve.
set -euo pipefail

RPC="${CT_CHAIN_RPC_URL:-http://anvil:8545}"

echo "Waiting for Anvil at ${RPC} ..."
until curl -fsS -X POST -H 'content-type: application/json' \
    --data '{"jsonrpc":"2.0","id":1,"method":"web3_clientVersion","params":[]}' \
    "${RPC}" >/dev/null 2>&1; do
  sleep 1
done
echo "Anvil is up."

if [ -z "$(find ml/artifacts -mindepth 1 -maxdepth 1 -type d 2>/dev/null)" ]; then
  echo "No trained model found; training one ..."
  python -m app.ml.train --rows 20000
fi

if [ -z "${CT_CONTRACT_ADDRESS:-}" ]; then
  echo "Deploying DecisionRegistry ..."
  CT_CONTRACT_ADDRESS="$(python -m scripts.deploy_local)"
  export CT_CONTRACT_ADDRESS
  echo "DecisionRegistry deployed at ${CT_CONTRACT_ADDRESS}"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
