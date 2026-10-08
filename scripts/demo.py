"""Self-contained end-to-end demo: train, deploy, score, anchor, verify.

Runs entirely in-process against an in-memory EVM (``eth-tester``) and a
temporary SQLite database, so ``python -m scripts.demo`` needs no Docker, no
Anvil and no network. It demonstrates the full decision lifecycle and that
tampering with a stored decision is detectable.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from web3 import EthereumTesterProvider, Web3

from app.chain.registry import Web3AnchorClient, deploy_registry
from app.db.session import init_engine
from app.ml.data import make_dataset, sample_applicant
from app.ml.model import CreditRiskModel
from app.service import ScoringService


def _rule() -> None:
    print("-" * 68)


def main() -> None:
    workdir = Path(tempfile.mkdtemp(prefix="credittrace-demo-"))

    print("1) Training model on synthetic data ...")
    model = CreditRiskModel(params={"n_estimators": 200})
    report = model.train(make_dataset(n=8_000, seed=42))
    model.save(workdir / "artifacts")
    print(f"   model {report.version} | ROC-AUC {report.metrics['roc_auc']:.3f}")

    print("2) Deploying DecisionRegistry to in-memory EVM ...")
    w3 = Web3(EthereumTesterProvider())
    deployer = w3.eth.accounts[0]
    address = deploy_registry(w3, deployer)
    anchor_client = Web3AnchorClient(w3, address, deployer)
    print(f"   registry at {address}")

    session_factory = init_engine(f"sqlite:///{workdir / 'demo.db'}")
    service = ScoringService(model, session_factory, anchor_client)

    print("3) Scoring an applicant ...")
    applicant = sample_applicant(seed=7)
    result = service.score(applicant)
    _rule()
    print(f"decision   : {result['decision'].upper()} (band={result['band']})")
    print(f"probability: {result['probability']:.4f}  ({result['score_bps']} bps)")
    print(f"digest     : {result['anchor']['digest']}")
    print(f"anchored   : block {result['anchor']['block_number']}")
    print("top reasons:")
    for reason in result["reasons"]:
        arrow = "+" if reason["direction"] == "increases_risk" else "-"
        print(f"   {arrow} {reason['label']}: {reason['value']} ({reason['contribution']:+.3f})")
    _rule()

    print("4) Verifying the decision against the chain ...")
    verdict = service.verify(result["decision_id"])
    print(f"   digest_matches={verdict['digest_matches']}  status={verdict['status']}")

    print("5) Tampering with the stored decision to prove detection ...")
    from app.db.models import Decision

    with session_factory() as db:
        row = db.get(Decision, result["decision_id"])
        row.applicant = {**row.applicant, "monthly_income": row.applicant["monthly_income"] * 10}
        db.add(row)
        db.commit()
    tampered = service.verify(result["decision_id"])
    print(
        f"   after tamper: digest_matches={tampered['digest_matches']}  status={tampered['status']}"
    )
    _rule()
    assert verdict["status"] == "verified"
    assert tampered["status"] == "digest_mismatch"
    print("OK: a genuine decision verifies; a tampered one is rejected.")


if __name__ == "__main__":
    main()
