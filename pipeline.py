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
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from policy import POLICIES, Costs, compare, decisions, evaluate

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
NUMERIC = ["log_amount", "overnight", "prior_hour_count", "amount_to_30d_avg",
           "log_seconds_since_prior", "new_category"]
CATEGORICAL = ["channel", "merchant_category"]
FEATURES = NUMERIC + CATEGORICAL
BASE_CAPACITY = 100


def synthetic_transactions(seed=42, days=90, daily_volume=6000):
    rng = np.random.default_rng(seed)
    count = days * daily_volume
    day = np.repeat(np.arange(days), daily_volume)
    card_id = rng.integers(1, 15001, count)
    incident = rng.random(count) < np.where(day < 65, 0.00125, 0.00185)
    channel = np.where(rng.random(count) < np.where(incident, 0.85, 0.40), "online", "in_person")
    category = rng.choice(["grocery", "fuel", "electronics", "travel", "other"], count)
    category = np.where(incident & (rng.random(count) < 0.6), "electronics", category)
    amount = np.clip(rng.lognormal(np.where(incident, 5.1, 3.7), 0.95), 1, 2500).round(2)
    hour = np.where(incident, rng.integers(0, 24, count), rng.integers(6, 24, count))
    seconds = day * 86400 + hour * 3600 + rng.integers(0, 3600, count)
    base = pd.DataFrame({
        "card_id": card_id, "seconds": seconds, "channel": channel,
        "merchant_category": category, "amount": amount,
        "is_fraud": (rng.random(count) < np.where(incident, 0.55, 0.00012)).astype(int),
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


def score_models(features):
    frame = features.assign(
        day=features["occurred_at"].str[:10],
        log_amount=np.log1p(features["amount"]),
        log_seconds_since_prior=np.log1p(features["seconds_since_prior"]),
    )
    days = frame["day"].unique()
    train = frame.loc[(frame["day"] >= days[30]) & (frame["day"] < days[50])]
    validation = frame.loc[(frame["day"] >= days[50]) & (frame["day"] < days[65])].copy()
    holdout = frame.loc[frame["day"] >= days[65]].copy()
    model_rows, calibration = [], []
    for name, estimator in [
        ("Logistic regression", LogisticRegression(max_iter=500)),
        ("HistGradientBoosting", HistGradientBoostingClassifier(
            max_iter=150, max_leaf_nodes=15, min_samples_leaf=100, random_state=42
        )),
    ]:
        transform = ColumnTransformer([
            ("numbers", make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                                      StandardScaler()), NUMERIC),
            ("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ])
        model = make_pipeline(transform, estimator).fit(train[FEATURES], train["is_fraud"])
        for label, split in [("validation", validation), ("holdout", holdout)]:
            risk = model.predict_proba(split[FEATURES])[:, 1]
            split[name] = risk
            model_rows.append({
                "model": name, "split": label, "fraud_rate": split["is_fraud"].mean(),
                "average_precision": average_precision_score(split["is_fraud"], risk),
                "brier_score": brier_score_loss(split["is_fraud"], risk),
            })
            for bucket, group in split.assign(
                risk=risk, decile=pd.qcut(pd.Series(risk, index=split.index).rank(method="first"), 10, labels=False) + 1
            ).groupby("decile"):
                calibration.append({
                    "model": name, "split": label, "decile": bucket, "transactions": len(group),
                    "mean_prediction": group["risk"].mean(), "observed_fraud_rate": group["is_fraud"].mean(),
                    "fraud_cases": int(group["is_fraud"].sum()),
                })
    return validation, holdout, pd.DataFrame(model_rows), pd.DataFrame(calibration)


def tune_thresholds(validation, costs):
    """Tune each action policy on validation; share tiers for a matched ranking comparison."""
    grid = (0.002, 0.005, 0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.0)
    best = {}
    for policy in ("Score threshold", "Tiered probability", "Tiered dollars"):
        candidates = (
            [(threshold, threshold) for threshold in grid] if policy == "Score threshold"
            else [(review, verify) for review in grid for verify in grid if verify <= review]
        )
        best[policy] = min(candidates, key=lambda pair: evaluate(
            decisions(validation, policy, BASE_CAPACITY, *pair), costs
        )["total_cost"])
    best["Rules only"] = (1.0, 1.0)
    return best


def bootstrap(actions, costs):
    """Pair policies by day and resample days with replacement."""
    daily = pd.DataFrame({
        policy: group.groupby("day").apply(
            lambda day: evaluate(day.assign(day=day.name), costs)["total_cost"], include_groups=False
        ) for policy, group in actions.items()
    })
    index = np.random.default_rng(42).integers(0, len(daily), size=(10000, len(daily)))
    rows = []
    for other in ("Score threshold", "Tiered probability", "Matched probability"):
        differences = (daily[other] - daily["Tiered dollars"]).to_numpy()
        low, high = np.quantile(differences[index].sum(axis=1), [0.025, 0.975])
        rows.append({"comparator": other, "savings": differences.sum(), "low_95": low, "high_95": high})
    return pd.DataFrame(rows)


def save_chart(frame, x, y, xlabel, path, *, usage=False):
    fig, ax = plt.subplots(figsize=(8.5, 5), layout="constrained")
    for policy, rows in frame.groupby("policy", sort=False):
        ax.plot(rows[x], rows[y], marker="o", linewidth=2, label=policy)
        if usage:
            for _, row in rows.iterrows():
                ax.annotate(str(int(row["capacity"])), (row[x], row[y]),
                            xytext=(4, 5), textcoords="offset points", fontsize=8)
    ax.set(xlabel=xlabel, ylabel="25-day estimated cost (USD)")
    ax.yaxis.set_major_formatter(lambda value, _: f"${value:,.0f}")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    RESULTS.mkdir(exist_ok=True)
    features, segments = sql_analysis(synthetic_transactions())
    validation, holdout, models, calibration = score_models(features)
    model = models.loc[models["split"].eq("validation")].sort_values(
        "average_precision", ascending=False
    ).iloc[0]["model"]
    for split in (validation, holdout):
        split["risk"] = split[model]
    costs = Costs()
    thresholds = tune_thresholds(validation, costs)
    comparison = pd.concat([
        compare(holdout, capacity, thresholds, costs).assign(capacity=capacity)
        for capacity in (25, 50, 100)
    ], ignore_index=True)
    actions = {
        policy: decisions(holdout, policy, BASE_CAPACITY, *thresholds[policy]) for policy in POLICIES
    }
    actions["Matched probability"] = decisions(
        holdout, "Tiered probability", BASE_CAPACITY, *thresholds["Tiered dollars"]
    )
    with sqlite3.connect(":memory:") as db:
        pd.concat([
            frame[["day", "action", "is_fraud"]].assign(policy=policy)
            for policy, frame in actions.items()
        ]).to_sql("policy_actions", db, index=False)
        monitoring = pd.read_sql_query((ROOT / "sql/monitoring.sql").read_text(), db)

    baseline = comparison.loc[comparison["capacity"].eq(BASE_CAPACITY)].copy()
    sensitivity = pd.concat([
        baseline.assign(
            total_cost=baseline["total_cost"] - baseline["friction_cost"]
            + baseline["friction_cost"] / costs.friction * fee,
            friction_assumption=fee,
        ) for fee in np.arange(0, 101, 1)
    ], ignore_index=True)
    reports = {
        "segments": segments, "policy_comparison": comparison, "sensitivity": sensitivity,
        "model_comparison": models, "calibration": calibration, "daily_monitoring": monitoring,
        "bootstrap": bootstrap(actions, costs),
    }
    for name, report in reports.items():
        report.round(8).to_csv(RESULTS / f"{name}.csv", index=False)
    metrics = {
        "selected_model": model, "thresholds": thresholds, "capacity": BASE_CAPACITY,
        "holdout_transactions": len(holdout), "holdout_fraud_cases": int(holdout["is_fraud"].sum()),
        "holdout_fraud_rate": holdout["is_fraud"].mean(),
    }
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    scenarios = pd.concat([
        compare(holdout, capacity, thresholds, costs).assign(capacity=capacity)
        for capacity in range(0, 251, 5)
    ], ignore_index=True)
    scenarios.round(8).to_csv(RESULTS / "dashboard_scenarios.csv", index=False)
    save_chart(comparison, "capacity", "total_cost", "Maximum reviews per day", RESULTS / "capacity.png")
    save_chart(comparison, "legit_challenges_per_1000", "total_cost",
               "Legitimate challenges per 1,000 (labels show daily capacity)",
               RESULTS / "friction_tradeoff.png", usage=True)
    print(baseline.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
