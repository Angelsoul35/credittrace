# Threat model (STRIDE)

Scope: the CreditTrace scoring service, its database, and the `DecisionRegistry`
contract. The goal is a decision record whose integrity can be proven later, without
exposing applicant data.

## Assets

* **Applicant data** — personal and financial fields (off-chain only).
* **Decision records** — score, reasons, outcome, digest (off-chain).
* **Decision digests** — the 32-byte values on the chain.
* **The scorer key** — the private key allowed to call `anchor`.

## Trust boundaries

1. Client -> API (input we do not trust).
2. API/service -> database.
3. Service -> chain RPC endpoint (holds the scorer key).
4. Contract access control (owner / scorers).

## STRIDE analysis

| Threat | How it could happen | How we handle it |
|---|---|---|
| **Spoofing** | Someone not allowed anchors fake digests | The contract only lets an allowed scorer call `anchor`; only the owner can grant that role. |
| **Tampering** | Someone edits a stored decision later | Verify rebuilds the digest from the stored record; any change gives `digest_mismatch`. The on-chain anchor is write-only and cannot be rewritten. |
| **Repudiation** | The lender denies a decision was made as shown | The anchored digest proves the exact decision existed at a given block; the `DecisionAnchored` events form an audit trail. |
| **Information disclosure** | Personal data leaks through the ledger | Only digests go on the chain; no applicant data ever reaches it ([ADR-0002](adr/0002-anchor-digest-not-data.md)). |
| **Denial of service** | Flooding `/score` or the RPC | The API is stateless and scales out; anchoring is idempotent per digest; the RPC and signer can be rate-limited. Out of scope for this reference project. |
| **Elevation of privilege** | A stolen scorer or owner key | Keys are configuration, never committed; `gitleaks` runs in CI; the owner can revoke a bad scorer with `setScorer(addr, false)`. A real deployment would use a KMS/HSM-backed signer. |

## Input validation

All request fields are range- and value-checked by Pydantic (`ApplicantIn`): age 18–100,
non-negative amounts, `debt_to_income` ≤ 3, and `region`/`loan_purpose` limited to known
values. Bad input is rejected with HTTP 422 before it reaches the model.

## Residual risks (accepted for a reference project)

* The off-chain database is the main record. Its backups and uptime are an operational
  task, not solved here.
* The demo uses Anvil's well-known development key, which is **public on purpose**. A
  real deployment must use a funded key from a secret manager and point the RPC at the
  real network.
* Model fairness is not checked here. A production lending model would need bias testing
  on protected groups.
