"""Evaluate review and verification policies on the public ULB benchmark."""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from policy import Costs, decisions, evaluate

RESULTS = Path(__file__).resolve().parent / "results"
POLICIES = ("Score threshold", "Tiered probability", "Tiered dollars")
CAPACITIES = (2, 5, 10, 15)
REFERENCE_CAPACITY = 5
FEATURES = [f"V{column}" for column in range(1, 29)] + ["log_amount"]


def load_transactions(path):
    frame = pd.read_csv(path).rename(columns={"Class": "is_fraud", "Amount": "amount"})
    frame["transaction_id"] = np.arange(len(frame))
    frame["hour"] = (frame["Time"] // 3600).astype(int)
    frame["log_amount"] = np.log1p(frame["amount"])
    return frame


def paired_hourly_bootstrap(dollar_actions, probability_actions, costs):
    """Resample matched hours to estimate the 20-hour ranking cost difference."""
    dollar_hours = dollar_actions.groupby("day")
    probability_hours = probability_actions.groupby("day")
    differences = np.array([
        evaluate(probability_hours.get_group(hour), costs)["total_cost"]
        - evaluate(actions, costs)["total_cost"]
        for hour, actions in dollar_hours
    ])
    draws = np.random.default_rng(42).integers(0, len(differences), (10_000, len(differences)))
    low, high = np.quantile(differences[draws].sum(axis=1), [0.025, 0.975])
    return {
        "estimated_savings": float(differences.sum()), "low_95": float(low),
        "high_95": float(high), "hour_blocks": len(differences), "replicates": len(draws),
    }


def benchmark(frame):
    train = frame.loc[frame["hour"] < 20]
    validation = frame.loc[frame["hour"].between(20, 27)].copy()
    holdout = frame.loc[frame["hour"] >= 28].copy()
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500))
    model.fit(train[FEATURES], train["is_fraud"])
    for split in (validation, holdout):
        split["risk"] = model.predict_proba(split[FEATURES])[:, 1]

    # The shared simulator groups by its queue window column (day in the sandbox).
    # Here each window is an elapsed hour and uses only that hour's queue budget.
    columns = ["transaction_id", "hour", "amount", "is_fraud", "risk"]
    validation_queue = validation[columns].rename(columns={"hour": "day"})
    holdout_queue = holdout[columns].rename(columns={"hour": "day"})
    costs = Costs()
    grid = (0.005, 0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 0.75, 1.0)
    thresholds = {}
    for policy in POLICIES:
        candidates = [
            (review, verify) for review in grid for verify in grid
            if verify <= review and (policy != "Score threshold" or verify == review)
        ]
        thresholds[policy] = min(candidates, key=lambda pair: evaluate(
            decisions(validation_queue, policy, REFERENCE_CAPACITY, *pair), costs
        )["total_cost"])
    # A matched probability policy uses the dollar policy's thresholds so the
    # difference between the two rows isolates ranking under the same actions.
    strategies = [
        *[(policy, policy, thresholds[policy]) for policy in POLICIES],
        ("Matched probability", "Tiered probability", thresholds["Tiered dollars"]),
    ]
    rows = []
    reference = {}
    for capacity in CAPACITIES:
        for label, policy, pair in strategies:
            actions = decisions(holdout_queue, policy, capacity, *pair)
            if capacity == REFERENCE_CAPACITY:
                reference[label] = actions
            summary = evaluate(actions, costs)
            summary["reviews_per_hour"] = summary.pop("reviews_per_day")
            rows.append({"reviews_per_hour_cap": capacity, "policy": label, **summary})
    no_verification_benefit = evaluate(
        reference["Tiered dollars"], replace(costs, verification_effectiveness=0)
    )
    metrics = {
        "transactions": len(frame), "fraud_cases": int(frame["is_fraud"].sum()),
        "training_transactions": len(train), "training_fraud_cases": int(train["is_fraud"].sum()),
        "validation_transactions": len(validation), "validation_fraud_cases": int(validation["is_fraud"].sum()),
        "holdout_transactions": len(holdout), "holdout_fraud_cases": int(holdout["is_fraud"].sum()),
        "holdout_hours": int(holdout["hour"].nunique()), "holdout_fraud_rate": holdout["is_fraud"].mean(),
        "holdout_average_precision": average_precision_score(holdout["is_fraud"], holdout["risk"]),
        "holdout_brier_score": brier_score_loss(holdout["is_fraud"], holdout["risk"]),
        "reference_reviews_per_hour": REFERENCE_CAPACITY, "validation_thresholds": thresholds,
        "matched_ranking_bootstrap": paired_hourly_bootstrap(
            reference["Tiered dollars"], reference["Matched probability"], costs
        ),
        "tiered_dollars_cost_at_zero_verification_effectiveness": float(
            no_verification_benefit["total_cost"]
        ),
    }
    return pd.DataFrame(rows), metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Path to the original ULB creditcard.csv")
    args = parser.parse_args()
    comparison, metrics = benchmark(load_transactions(args.csv))
    with args.csv.open("rb") as source:
        metrics["source_sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
    RESULTS.mkdir(exist_ok=True)
    comparison.round(8).to_csv(RESULTS / "public_policy_comparison.csv", index=False)
    (RESULTS / "public_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    print(comparison[["reviews_per_hour_cap", "policy", "total_cost",
                      "legit_challenges_per_1000", "peak_reviews"]].to_string(index=False))


if __name__ == "__main__":
    main()
