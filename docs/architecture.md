# Architecture

## Goal

Score microloan applications in a way that is **explainable** to a credit officer and
**tamper-evident** to an auditor, without leaking applicant data onto a public ledger.

## Components

| Layer | Module | Responsibility |
|---|---|---|
| ML | `app/ml` | Feature contract, synthetic data, XGBoost pipeline, SHAP explanations, versioned artifact store |
| Chain | `app/chain` | Canonical payload + `keccak256` digest, contract compilation (solc-js), anchor clients |
| Persistence | `app/db` | SQLAlchemy `Decision` model and session management |
| Orchestration | `app/service.py` | `ScoringService`: score → persist → anchor → verify |
| API | `app/main.py` | FastAPI endpoints |
| Contract | `contracts/` | `DecisionRegistry.sol`, solc-js compiler, Foundry tests |

## Decision lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI
    participant S as ScoringService
    participant M as Model (XGBoost+SHAP)
    participant DB as PostgreSQL
    participant CH as DecisionRegistry (EVM)

    C->>API: POST /score {applicant}
    API->>S: score(applicant)
    S->>M: predict_proba + explain
    M-->>S: probability, reasons
    S->>S: band/action = policy(score)
    S->>S: digest = keccak256(canonical payload)
    S->>CH: is_anchored(digest)?
    alt not anchored
        S->>CH: anchor(digest)
        CH-->>S: tx, block
    else already anchored
        CH-->>S: existing record
    end
    S->>DB: INSERT decision (+ digest, anchor info)
    S-->>API: decision + reasons + anchor
    API-->>C: 200 ScoreResponse
```

## The canonical payload

The digest binds everything needed to reproduce a decision:

```
payload = json(sort_keys, no-whitespace) {
    "decision":      "approve" | "review" | "decline",
    "features":      { ...the exact scored features... },
    "model_version": "m_<hash>",
    "score_bps":     <int, probability * 10000>
}
digest = keccak256(payload)       # 32 bytes
```

Canonical serialisation (sorted keys, no insignificant whitespace) guarantees the same
decision always yields the same digest and any change yields a different one. See
[ADR-0003](adr/0003-canonical-serialization.md).

## The contract

`DecisionRegistry` is deliberately minimal: a role-gated, append-only registry mapping
`bytes32` digest → `{submitter, timestamp, blockNumber}`.

* `anchor(digest)` — only an authorised scorer; reverts on a zero digest or a
  re-anchor (`AlreadyAnchored`).
* `recordOf(digest)` / `isAnchored(digest)` — public reads used by verification.
* `setScorer` / `transferOwnership` — owner-gated access control.

It never receives applicant data ([ADR-0002](adr/0002-anchor-digest-not-data.md)).

## Dependency inversion for the chain

`ScoringService` depends on the `AnchorClient` **protocol**, not on web3:

```
AnchorClient (Protocol)
├── Web3AnchorClient      # real contract, works on Anvil or in-memory PyEVM
└── InMemoryAnchorClient  # dict-backed fake, mirrors contract semantics
```

This is what makes the system testable without any blockchain and lets anchoring be
switched off entirely (`CT_CHAIN_ENABLED=false`) for offline scoring.

## Verification & tamper evidence

`GET /decisions/{id}/verify`:

1. Recompute the digest from the **stored** record.
2. Compare it to the stored digest → `digest_matches`.
3. Look the digest up on-chain → `on_chain.anchored`.

| Outcome | Meaning |
|---|---|
| `verified` | digest matches and is anchored on-chain |
| `digest_mismatch` | a stored field was altered after the decision was made |
| `not_anchored` | digest matches but was never anchored |
| `chain_disabled` | anchoring was off when scored |

## Configuration

All configuration is environment-driven (`CT_` prefix, see `.env.example`): database
URL, model directory and pinned version, chain enablement, RPC URL, contract address,
signing key, and the risk-band thresholds.

## Deployment shape

`docker-compose.yml` runs PostgreSQL, Anvil and the API. The API entrypoint waits for
Anvil, trains a model if none exists, deploys the registry if no address is configured,
then serves. In production the RPC URL and a funded signing key would point at the
target network and the model artifact would be built in CI and shipped read-only.
