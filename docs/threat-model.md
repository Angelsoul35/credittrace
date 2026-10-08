# Threat model (STRIDE)

Scope: the CreditTrace scoring service, its database, and the `DecisionRegistry`
contract. The goal is a decision record whose integrity can be proven after the fact
without exposing applicant data.

## Assets

* **Applicant data** — personal and financial fields (off-chain only).
* **Decision records** — score, reasons, outcome, digest (off-chain).
* **Decision digests** — 32-byte anchors (on-chain).
* **The scorer key** — the private key authorised to call `anchor`.

## Trust boundaries

1. Client → API (untrusted input).
2. API/service → database.
3. Service → chain RPC endpoint (holds the scorer key).
4. Contract access control (owner / scorers).

## STRIDE analysis

| Threat | Vector | Mitigation |
|---|---|---|
| **Spoofing** | Unauthorised caller anchors forged digests | Contract gates `anchor` behind `isScorer`; only the owner can grant that role. |
| **Tampering** | Someone edits a stored decision after the fact | Verification recomputes the digest from the stored record; any change yields `digest_mismatch`. The on-chain anchor is append-only and cannot be rewritten. |
| **Repudiation** | Lender denies a decision was made as shown | The anchored digest proves the exact decision existed at a specific block; `DecisionAnchored` events form an audit trail. |
| **Information disclosure** | PII leaks via the ledger | Only digests are anchored; no applicant data ever reaches the chain ([ADR-0002](adr/0002-anchor-digest-not-data.md)). |
| **Denial of service** | Flooding `/score` or the RPC | Stateless API scales horizontally; anchoring is idempotent per digest; RPC/signing can be rate-limited and queued. Out of scope for this reference implementation. |
| **Elevation of privilege** | Stolen scorer key or owner key | Keys are configuration, never committed; `gitleaks` runs in CI; the owner can revoke a compromised scorer with `setScorer(addr, false)`. Production would use a KMS/HSM-backed signer. |

## Input validation

All request fields are range- and enum-checked by Pydantic (`ApplicantIn`): age
18–100, non-negative amounts, `debt_to_income` ≤ 3, `region`/`loan_purpose` restricted
to known values. Invalid input is rejected with HTTP 422 before it reaches the model.

## Residual risks (accepted for a reference implementation)

* The off-chain database is the system of record; its availability and backups are an
  operational concern, not solved here.
* The demo uses Anvil's well-known development key, which is **public by design**. A
  real deployment must use a funded key from a secret manager and point the RPC at the
  target network.
* Model fairness and bias are not audited here; a production lending model would
  require disparate-impact testing on protected attributes.
