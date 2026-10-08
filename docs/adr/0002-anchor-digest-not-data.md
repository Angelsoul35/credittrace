# ADR-0002: Anchor a digest, never applicant data

* Status: accepted
* Date: 2026-01-16

## Context

The integrity guarantee requires putting *something* about each decision on a ledger.
Applicant data is personal and, under Colombian Law 1581 (Habeas Data) and comparable
regimes, must not be exposed. A blockchain record is effectively permanent and, on a
public chain, world-readable.

## Decision

The contract stores only a 32-byte `keccak256` digest of the canonical decision
payload. All personal and financial data stays in the off-chain database. Verification
works by recomputing the digest from the stored record and checking it against the
chain.

## Consequences

* **Positive:** integrity is provable with zero on-chain PII; the record is small and
  cheap; the same scheme works on a public chain without privacy review.
* **Negative:** the chain alone cannot reconstruct a decision — it only confirms a
  digest. The authoritative data lives off-chain and must be retained. This is the
  correct trade-off: the chain is a notary, not a data store.
