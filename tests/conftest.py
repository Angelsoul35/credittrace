"""Shared pytest fixtures.

The model is trained once per test session on a small synthetic dataset. The
chain fixtures deploy the real compiled contract to an in-memory PyEVM node via
``eth-tester`` — no Anvil or network required.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from web3 import EthereumTesterProvider, Web3

from app.chain.registry import Web3AnchorClient, deploy_registry
from app.db.session import init_engine
from app.ml.data import make_dataset, sample_applicant
from app.ml.model import CreditRiskModel
from app.service import ScoringService


@pytest.fixture(scope="session")
def model(tmp_path_factory) -> CreditRiskModel:
    artifact_dir = tmp_path_factory.mktemp("artifacts")
    trained = CreditRiskModel(params={"n_estimators": 150})
    trained.train(make_dataset(n=4_000, seed=123))
    trained.save(artifact_dir)
    return CreditRiskModel.load(artifact_dir)


@pytest.fixture
def applicant() -> dict:
    return sample_applicant(seed=7)


@pytest.fixture
def w3() -> Web3:
    return Web3(EthereumTesterProvider())


@pytest.fixture
def anchor_client(w3: Web3) -> Web3AnchorClient:
    account = w3.eth.accounts[0]
    address = deploy_registry(w3, account)
    return Web3AnchorClient(w3, address, account)


@pytest.fixture
def session_factory(tmp_path):
    return init_engine(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def service(model, session_factory, anchor_client) -> ScoringService:
    return ScoringService(model, session_factory, anchor_client)


@pytest.fixture
def client(service) -> TestClient:
    from app.deps import get_service
    from app.main import app

    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
