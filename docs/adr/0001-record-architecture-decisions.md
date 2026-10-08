# ADR-0001: Record architecture decisions

* Status: accepted
* Date: 2026-01-15

## Context

CreditTrace makes several non-obvious design choices (anchoring decisions on-chain,
storing only digests, a canonical serialisation). Future readers — including the
author revisiting the project — need the *why*, not just the *what*.

## Decision

We keep lightweight Architecture Decision Records (ADRs) in `docs/adr/`, one per
significant decision, in the Nygard format: Context, Decision, Consequences.

## Consequences

* Decisions are traceable and reviewable.
* The cost is small: a short Markdown file per decision.
