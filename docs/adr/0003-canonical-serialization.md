# ADR-0003: Canonical JSON serialisation for the digest

* Status: accepted
* Date: 2026-01-16

## Context

A digest is only meaningful if the same decision always produces the same bytes.
Plain `json.dumps` is not canonical: key order and whitespace vary, so two logically
identical decisions could hash differently, breaking verification.

## Decision

The canonical payload is produced with `json.dumps(obj, sort_keys=True,
separators=(",", ":"))` over a fixed object shape (`decision`, `features`,
`model_version`, `score_bps`). The score is stored as an integer (basis points) to
avoid floating-point representation drift.

## Consequences

* **Positive:** deterministic, language-agnostic digests; any field change is
  detectable; an independent re-implementation can reproduce the digest.
* **Negative:** the payload shape is now part of the contract: changing it changes
  all future digests, so it is versioned implicitly through `model_version` and treated
  as stable.
