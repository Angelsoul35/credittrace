# Datasets

## `german_credit.csv` — UCI Statlog (German Credit Data)

A **real**, public credit-risk dataset: 1,000 loan applicants described by 20
attributes, each labelled good or bad credit risk. It is one of the canonical
benchmarks for credit scoring and is used here to validate the modelling and
explainability approach on real applicants, not only on the synthetic generator.

| | |
|---|---|
| **Origin** | UCI Machine Learning Repository — *Statlog (German Credit Data)* |
| **Donor** | Prof. Hans Hofmann, Universität Hamburg |
| **Rows / columns** | 1,000 / 21 (20 features + target) |
| **Class balance** | 700 good (`credit_risk = 1`), 300 bad (`credit_risk = 0`) |
| **Mirror used** | `https://raw.githubusercontent.com/selva86/datasets/master/GermanCredit.csv` |
| **Retrieved** | 2026-10-09 |
| **License** | Creative Commons Attribution 4.0 (UCI) |

The file is **vendored** (committed to the repo) so training and tests are
deterministic and run offline. It is the human-readable recoding of the original
Statlog data (category codes replaced by their meanings, e.g. `A11 -> "... < 0 DM"`).

### Target

The column `credit_risk` is `1` for good and `0` for bad. The loader
(`app/ml/real_data.py`) derives `default = (credit_risk == 0)`, so the **positive
class is the bad credit / default** — the event a lender wants to predict.

### How it is used

`python -m app.ml.benchmark` trains the same XGBoost + one-hot + SHAP architecture
used by the main model on this real data, reports cross-validated ROC-AUC / KS /
Brier against a logistic-regression baseline, and lists the SHAP global drivers.
Expected ROC-AUC is ~0.74–0.80 (literature-consistent) — **not** a suspicious 1.0.

### Refreshing the file

```bash
python -c "from app.ml.real_data import fetch; fetch()"   # re-downloads from the mirror
```
