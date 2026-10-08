"""Train the credit-risk model and register a versioned artifact.

Usage::

    python -m app.ml.train                 # 20k synthetic rows -> ml/artifacts/<version>
    python -m app.ml.train --rows 50000
"""

from __future__ import annotations

import argparse

from app.config import get_settings
from app.ml.data import make_dataset
from app.ml.model import CreditRiskModel


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Train the CreditTrace risk model.")
    parser.add_argument("--rows", type=int, default=20_000, help="synthetic applicants")
    parser.add_argument("--seed", type=int, default=42, help="dataset seed")
    parser.add_argument("--model-dir", default=settings.model_dir, help="artifact root")
    args = parser.parse_args()

    print(f"Generating {args.rows:,} synthetic applicants (seed={args.seed}) ...")
    df = make_dataset(n=args.rows, seed=args.seed)

    print("Training XGBoost pipeline ...")
    model = CreditRiskModel()
    report = model.train(df)
    path = model.save(args.model_dir)

    print("\n=== Training report ===")
    print(f"version      : {report.version}")
    print(f"rows         : {report.n_rows:,}")
    print(f"default rate : {report.default_rate:.1%}")
    print(f"ROC-AUC      : {report.metrics['roc_auc']:.4f}")
    print(f"KS           : {report.metrics['ks']:.4f}")
    print(f"Brier        : {report.metrics['brier']:.4f}")
    print(f"artifact     : {path}")


if __name__ == "__main__":
    main()
