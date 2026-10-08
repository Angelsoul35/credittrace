# ADR-0004: Explain decisions with SHAP, aggregated to real features

* Status: accepted
* Date: 2026-01-17

## Context

A credit decision must be explainable in terms a human understands. The model consumes
one-hot-encoded columns (`region_caribe`, …), which are meaningless to a credit officer.

## Decision

We use `shap.TreeExplainer` on the fitted XGBoost model and **aggregate** the SHAP
contributions of one-hot columns back to their parent feature (all `region_*` sum into
`region`). Each decision returns the top-k features by absolute contribution, each with
a signed value and a direction (`increases_risk` / `decreases_risk`).

## Consequences

* **Positive:** explanations are in real features; they are consistent with the model's
  real behaviour (SHAP adds up to the prediction and follows the model), not a story made up afterward.
* **Negative:** SHAP adds compute per request; acceptable for the microloan throughput
  this system targets, and the explainer is built once and reused.
