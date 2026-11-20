"""Generate synthetic transactions, fit a risk model, and run the backtest."""

import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from policy import Costs, compare, decisions, evaluate

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FEATURES = ["log_amount", "overnight", "prior_hour_count", "channel", "merchant_category"]


def synthetic_transactions(seed=42, days=90, daily_volume=2400):
    rng = np.random.default_rng(seed)
    count = days * daily_volume
    day = np.repeat(np.arange(days), daily_volume)
    card_id = rng.integers(1, 15001, count)
    incident = rng.random(count) < np.where(day < 65, 0.027, 0.043)
    channel = np.where(rng.random(count) < np.where(incident, 0.85, 0.40), "online", "in_person")
    category = rng.choice(["grocery", "fuel", "electronics", "travel", "other"], count)
    category = np.where(incident & (rng.random(count) < 0.6), "electronics", category)
    amount = np.clip(rng.lognormal(np.where(incident, 5.1, 3.7), 0.95), 1, 2500).round(2)
    hour = np.where(incident, rng.integers(0, 24, count), rng.integers(6, 24, count))
    seconds = day * 86400 + hour * 3600 + rng.integers(0, 3600, count)
    base = pd.DataFrame({
        "card_id": card_id, "seconds": seconds, "channel": channel,
        "merchant_category": category, "amount": amount,
        "is_fraud": (rng.random(count) < np.where(incident, 0.55, 0.0015)).astype(int),
    })
    # Add card-level bursts, including legitimate bursts as well as fraud.
    burst_seeds = base.loc[(incident & (rng.random(count) < 0.11)) | (rng.random(count) < 0.005)]
    followups = burst_seeds.loc[burst_seeds.index.repeat(3)].copy()
    followups["seconds"] += rng.integers(30, 1800, len(followups))
    followups["amount"] = (followups["amount"] * rng.uniform(0.55, 1.25, len(followups))).round(2)
    transactions = pd.concat([base, followups], ignore_index=True)
    transactions = transactions.loc[transactions["seconds"] < days * 86400].reset_index(drop=True)
    transactions.insert(0, "transaction_id", np.arange(1, len(transactions) + 1))
    transactions["occurred_at"] = (
        pd.Timestamp("2025-01-01") + pd.to_timedelta(transactions.pop("seconds"), unit="s")
    ).dt.strftime("%Y-%m-%d %H:%M:%S")
    return transactions


def sql_analysis(transactions):
    with sqlite3.connect(":memory:") as db:
        transactions.to_sql("transactions", db, index=False)
        db.execute("CREATE INDEX card_time ON transactions (card_id, occurred_at)")
        features = pd.read_sql_query((ROOT / "sql/features.sql").read_text(), db)
        segments = pd.read_sql_query((ROOT / "sql/segments.sql").read_text(), db)
    return features, segments


def scored_holdout(features):
    frame = features.assign(day=features["occurred_at"].str[:10], log_amount=np.log1p(features["amount"]))
    days = frame["day"].unique()
    train_end = days[50]
    test_start = days[65]
    train = frame.loc[frame["day"] < train_end]
    validation = frame.loc[(frame["day"] >= train_end) & (frame["day"] < test_start)].copy()
    holdout = frame.loc[frame["day"] >= test_start].copy()
    transform = ColumnTransformer([
        ("numbers", StandardScaler(), FEATURES[:3]),
        ("categories", OneHotEncoder(handle_unknown="ignore"), FEATURES[3:]),
    ])
    model = make_pipeline(transform, LogisticRegression(max_iter=500))
    model.fit(train[FEATURES], train["is_fraud"])
    for split in (validation, holdout):
        split["risk"] = model.predict_proba(split[FEATURES])[:, 1]
    metrics = {
        "train_end_exclusive": train_end,
        "test_start_inclusive": test_start,
        "holdout_transactions": len(holdout),
        "holdout_fraud_cases": int(holdout["is_fraud"].sum()),
        "holdout_fraud_rate": float(holdout["is_fraud"].mean()),
        "average_precision": average_precision_score(holdout["is_fraud"], holdout["risk"]),
        "brier_score": brier_score_loss(holdout["is_fraud"], holdout["risk"]),
    }
    return validation, holdout, metrics


def main():
    RESULTS.mkdir(exist_ok=True)
    features, segments = sql_analysis(synthetic_transactions())
    validation, holdout, metrics = scored_holdout(features)
    costs = Costs()
    candidates = []
    for review in (0.05, 0.10, 0.15, 0.25):
        for verify in (0.02, 0.04, 0.08, 0.12):
            if verify >= review:
                continue
            actions = decisions(validation, "Tiered dollars", 100, review, verify)
            candidates.append((evaluate(actions, costs)["total_cost"], review, verify))
    _, review, verify = min(candidates)
    metrics.update(review_threshold=review, verify_threshold=verify)
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    segments.to_csv(RESULTS / "segments.csv", index=False)
    holdout.drop(columns="log_amount").to_csv(RESULTS / "scored.csv", index=False)
    comparison = pd.concat([
        compare(holdout, cap, review, verify, costs).assign(capacity=cap)
        for cap in (50, 100, 200)
    ], ignore_index=True)
    comparison.round(4).to_csv(RESULTS / "policy_comparison.csv", index=False)

    sensitivity = pd.concat([
        compare(holdout, 100, review, verify, Costs(verification_effectiveness=rate))
        .assign(verification_effectiveness=rate)
        for rate in (0.00, 0.25, 0.45, 0.65, 0.85)
    ], ignore_index=True)
    sensitivity.round(4).to_csv(RESULTS / "sensitivity.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.8), layout="constrained")
    for policy, rows in comparison.groupby("policy", sort=False):
        ax.plot(rows["capacity"], rows["total_cost"], marker="o", linewidth=2, label=policy)
    ax.set(title="Estimated cost across review capacity", xlabel="Maximum reviews per day",
           ylabel="25-day simulated cost (USD)", xticks=[50, 100, 200])
    ax.yaxis.set_major_formatter(lambda x, _: f"${x:,.0f}")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.savefig(RESULTS / "capacity.png", dpi=160)
    print(comparison.loc[comparison["capacity"] == 100].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
