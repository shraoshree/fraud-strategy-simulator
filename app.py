"""Explore policy results for the ULB benchmark and synthetic sandbox."""

import json
from math import isclose
from pathlib import Path

import pandas as pd
import streamlit as st

from policy import Costs

RESULTS = Path(__file__).resolve().parent / "results"

st.set_page_config(page_title="Fraud Strategy Simulator", layout="wide")
st.title("Credit Card Fraud Strategy Simulator")

@st.cache_data
def load_scenarios(filename):
    return pd.read_csv(RESULTS / filename)


st.sidebar.header("Scenario")
dataset = st.sidebar.radio("Dataset", ["Synthetic sandbox", "Public ULB benchmark"])
public = dataset == "Public ULB benchmark"
if public:
    st.caption("Anonymized ULB card transactions · 20-hour holdout · Amounts in dataset currency units")
    capacity = st.sidebar.select_slider("Maximum reviews per hour", options=[2, 5, 10, 15], value=5)
    scenarios = load_scenarios("public_policy_comparison.csv")
    capacity_column, window, units = "reviews_per_hour_cap", "hour", "currency units"
    baseline_policy = "Score threshold"
else:
    st.caption("Synthetic 25-day holdout · Four policies with validation-tuned thresholds")
    capacity = st.sidebar.slider("Maximum reviews per day", 0, 50, 25, 5)
    st.sidebar.caption("Try 10, 15, 20, or 25 slots to see the ranking tradeoff when the queue fills.")
    scenarios = load_scenarios("dashboard_scenarios.csv")
    capacity_column, window, units = "capacity", "day", "USD"
    baseline_policy = "Rules only"

fee = st.sidebar.slider(f"Verification cost per transaction ({units})", 0.0, 8.0, 0.75, 0.25)
effectiveness = st.sidebar.slider("Fraud amount prevented by verification (%)", 0, 100, 65, 5)
friction = st.sidebar.slider(f"Extra cost per legitimate challenge ({units})", 0.0, 100.0, 2.0, 0.5)
costs = Costs(verification=fee, verification_effectiveness=effectiveness / 100, friction=friction)
comparison = scenarios.loc[scenarios[capacity_column].eq(capacity)].copy()
comparison["fraud_prevented"] = (
    costs.review_effectiveness * comparison["review_fraud_dollars"]
    + costs.verification_effectiveness * comparison["verification_fraud_dollars"]
)
comparison["residual_fraud"] = comparison["fraud_exposure"] - comparison["fraud_prevented"]
comparison["action_cost"] = costs.review * comparison["reviews"] + costs.verification * comparison["verifications"]
comparison["friction_cost"] = costs.friction * comparison["legitimate_challenged"]
comparison["total_cost"] = comparison[["residual_fraud", "action_cost", "friction_cost"]].sum(axis=1)
comparison = comparison.sort_values("total_cost", ignore_index=True)
best = comparison.iloc[0]
baseline = comparison.set_index("policy").loc[baseline_policy]
symbol = "" if public else "$"

first, second, third = st.columns(3)
first.metric("Lowest estimated total cost", f"{symbol}{best.total_cost:,.0f}",
             f"{symbol}{baseline.total_cost - best.total_cost:,.0f} below {baseline_policy.lower()}")
winners = comparison.loc[comparison["total_cost"].map(
    lambda cost: isclose(cost, best.total_cost, abs_tol=0.005)
), "policy"].tolist()
second.metric("Lowest-cost policy", "Tie" if len(winners) > 1 else winners[0])
if len(winners) > 1:
    second.caption(" and ".join(winners))
third.metric("Legitimate challenges per 1,000", f"{best.legit_challenges_per_1000:.1f}")

st.subheader("Policy comparison")
st.bar_chart(comparison, x="policy", y="total_cost", y_label=f"Estimated cost ({units})")
columns = {
    "policy": "Policy", "total_cost": f"Total cost ({units})", "residual_fraud": f"Residual fraud ({units})",
    "fraud_prevented": f"Fraud prevented ({units})", "legit_challenges_per_1000": "Legitimate challenges per 1,000",
    f"reviews_per_{window}": f"Reviews per {window}", "peak_reviews": f"Peak reviews per {window}",
    "verifications": "Verifications",
}
st.dataframe(comparison[list(columns)].rename(columns=columns).round(2), hide_index=True)
st.download_button("Download scenario results", comparison.to_csv(index=False), "fraud-policy-scenario.csv", "text/csv")

with st.expander("Cost assumptions"):
    st.write(
        "Total cost adds remaining fraud losses, handling costs, and the modeled cost of legitimate customer friction. "
        f"Each manual review costs 4 {units} and is assumed to prevent 90% of associated fraud amounts. "
        f"The simulator ranks each {window} of transactions as a batch."
    )

if public:
    with st.expander("Public data and model evaluation"):
        metrics = json.loads((RESULTS / "public_metrics.json").read_text())
        st.write(
            f"Holdout: {metrics['holdout_transactions']:,} transactions and "
            f"{metrics['holdout_fraud_cases']} labeled fraud cases. "
            f"Logistic regression average precision: {metrics['holdout_average_precision']:.3f}."
        )
        st.write(
            "The ULB data has elapsed time, amount, and anonymized features. "
            "It has no card history, channels, or recorded intervention outcomes."
        )
        interval = metrics["matched_ranking_bootstrap"]
        st.write(
            f"At baseline assumptions and {metrics['reference_reviews_per_hour']} review slots per hour, "
            f"the estimated matched ranking savings were {interval['estimated_savings']:,.0f} currency units "
            f"(rough 95% interval {interval['low_95']:,.0f} to {interval['high_95']:,.0f}; "
            f"{interval['hour_blocks']} paired hourly blocks)."
        )
        st.link_button("View the ULB source dataset", "https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud")
else:
    with st.expander("Model calibration and uncertainty"):
        calibration = pd.read_csv(RESULTS / "calibration.csv")
        st.write("Highest score decile")
        st.dataframe(calibration.loc[calibration["decile"].eq(10)].round(5), hide_index=True)
        st.write("Paired daily bootstrap at baseline costs and effectiveness")
        st.dataframe(pd.read_csv(RESULTS / "bootstrap.csv").round(2), hide_index=True)
