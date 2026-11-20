"""Interactive analysis of the same holdout used in the decision memo."""

import json

import pandas as pd
import streamlit as st

from pipeline import RESULTS
from policy import Costs, compare

st.set_page_config(page_title="Fraud Strategy Simulator", layout="wide")
st.title("Credit Card Fraud Strategy Simulator")

scored_path = RESULTS / "scored.csv"
if not scored_path.exists():
    st.info("Run `python pipeline.py` from the project folder to generate the dashboard data.")
    st.stop()


@st.cache_data
def load_scored(updated_at):
    return pd.read_csv(scored_path)


scored = load_scored(scored_path.stat().st_mtime_ns)
metrics = json.loads((RESULTS / "metrics.json").read_text())
st.caption(
    f"Synthetic holdout · {len(scored):,} transactions · "
    f"{scored['day'].min()} through {scored['day'].max()}"
)

st.sidebar.header("Scenario")
capacity = st.sidebar.slider("Maximum reviews per day", 0, 250, 100, 10)
fee = st.sidebar.slider("Verification cost per transaction ($)", 0.0, 8.0, 0.75, 0.25)
effectiveness = st.sidebar.slider("Fraud dollars prevented by verification (%)", 0, 100, 65, 5)
friction = st.sidebar.slider("Extra cost per legitimate challenge ($)", 0.0, 20.0, 2.0, 0.5)
costs = Costs(verification=fee, verification_effectiveness=effectiveness / 100, friction=friction)
comparison = compare(scored, capacity, metrics["review_threshold"], metrics["verify_threshold"], costs)
best = comparison.iloc[0]
rules = comparison.set_index("policy").loc["Rules only"]

first, second, third = st.columns(3)
first.metric("Lowest estimated total cost", f"${best.total_cost:,.0f}", f"${rules.total_cost - best.total_cost:,.0f} below rules")
second.metric("Lowest-cost policy", best.policy)
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
