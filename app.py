"""Interactive analysis of the same holdout used in the decision memo."""

from math import isclose
from pathlib import Path

import pandas as pd
import streamlit as st

from policy import Costs

RESULTS = Path(__file__).resolve().parent / "results"

st.set_page_config(page_title="Fraud Strategy Simulator", layout="wide")
st.title("Credit Card Fraud Strategy Simulator")

@st.cache_data
def load_scenarios():
    return pd.read_csv(RESULTS / "dashboard_scenarios.csv")


st.caption("Synthetic 25-day holdout · Four policies with validation-tuned thresholds")
st.sidebar.header("Scenario")
capacity = st.sidebar.slider("Maximum reviews per day", 0, 250, 100, 5)
st.sidebar.caption("Try 10, 15, 20, or 25 slots to see the ranking tradeoff when the queue fills.")
fee = st.sidebar.slider("Verification cost per transaction ($)", 0.0, 8.0, 0.75, 0.25)
effectiveness = st.sidebar.slider("Fraud dollars prevented by verification (%)", 0, 100, 65, 5)
friction = st.sidebar.slider("Extra cost per legitimate challenge ($)", 0.0, 100.0, 2.0, 0.5)
costs = Costs(verification=fee, verification_effectiveness=effectiveness / 100, friction=friction)
comparison = load_scenarios().loc[lambda table: table["capacity"].eq(capacity)].copy()
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
rules = comparison.set_index("policy").loc["Rules only"]

first, second, third = st.columns(3)
first.metric("Lowest estimated total cost", f"${best.total_cost:,.0f}", f"${rules.total_cost - best.total_cost:,.0f} below rules")
winners = comparison.loc[comparison["total_cost"].map(
    lambda cost: isclose(cost, best.total_cost, abs_tol=0.005)
), "policy"].tolist()
second.metric("Lowest-cost policy", "Tie" if len(winners) > 1 else winners[0])
if len(winners) > 1:
    second.caption(" and ".join(winners))
third.metric("Legitimate challenges per 1,000", f"{best.legit_challenges_per_1000:.1f}")

st.subheader("Policy comparison")
st.bar_chart(comparison, x="policy", y="total_cost", y_label="Estimated cost (USD)")
columns = {
    "policy": "Policy", "total_cost": "Total cost ($)", "residual_fraud": "Residual fraud ($)",
    "fraud_prevented": "Fraud prevented ($)", "legit_challenges_per_1000": "Legitimate challenges per 1,000",
    "reviews_per_day": "Reviews per day", "peak_reviews": "Peak daily reviews",
    "verifications": "Verifications",
}
st.dataframe(comparison[list(columns)].rename(columns=columns).round(2), hide_index=True)
st.download_button("Download scenario results", comparison.to_csv(index=False), "fraud-policy-scenario.csv", "text/csv")

with st.expander("Cost assumptions"):
    st.write(
        "Total cost adds remaining fraud losses, handling costs, and the modeled cost of legitimate customer friction. "
        "Each manual review costs $4 and is assumed to prevent 90% of the associated fraud dollars. "
        "The simulator ranks a full day of transactions as a batch."
    )

with st.expander("Model calibration and uncertainty"):
    calibration = pd.read_csv(RESULTS / "calibration.csv")
    st.write("Highest score decile")
    st.dataframe(calibration.loc[calibration["decile"].eq(10)].round(5), hide_index=True)
    st.write("Paired daily bootstrap at the baseline assumptions and 100 reviews per day")
    st.dataframe(pd.read_csv(RESULTS / "bootstrap.csv").round(2), hide_index=True)
