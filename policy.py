"""Apply transaction actions and estimate costs on labeled holdout data."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

POLICIES = ("Rules only", "Score threshold", "Tiered probability", "Tiered dollars")


@dataclass(frozen=True)
class Costs:
    review: float = 4.0
    verification: float = 0.75
    friction: float = 2.0
    review_effectiveness: float = 0.90
    verification_effectiveness: float = 0.65


def decisions(scored, policy, capacity, review_threshold, verify_threshold):
    """Rank each day's eligible alerts and route capacity overflow explicitly."""
    if capacity < 0 or not 0 <= verify_threshold <= review_threshold <= 1:
        raise ValueError("Use nonnegative capacity and ordered thresholds in [0, 1].")
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy: {policy}")

    ranked = scored.copy()
    ranked["action"] = "approve"
    ranked["priority"] = ranked["risk"]
    eligible = ranked["risk"] >= review_threshold
    if policy == "Rules only":
        eligible = (
            ((ranked["channel"] == "online") & (ranked["amount"] >= 150))
            | (ranked["prior_hour_count"] >= 2)
        )
        ranked["priority"] = ranked["amount"]
    if policy.startswith("Tiered"):
        ranked.loc[ranked["risk"] >= verify_threshold, "action"] = "verify"
    if policy == "Tiered dollars":
        ranked["priority"] *= ranked["amount"]

    alerts = ranked.loc[eligible].sort_values(
        ["day", "priority", "transaction_id"], ascending=[True, False, True]
    )
    reviewed = alerts.groupby("day", sort=False).head(capacity)
    ranked.loc[reviewed.index, "action"] = "review"
    return ranked.drop(columns="priority")


def evaluate(actions, costs):
    fraud = actions["is_fraud"].eq(1)
    review = actions["action"].eq("review")
    verify = actions["action"].eq("verify")
    effectiveness = np.select(
        [review, verify], [costs.review_effectiveness, costs.verification_effectiveness]
    )
    fraud_amount = actions["amount"] * fraud
    prevented = (fraud_amount * effectiveness).sum()
    residual = fraud_amount.sum() - prevented
    legitimate_challenged = ((review | verify) & ~fraud).sum()
    actions_cost = review.sum() * costs.review + verify.sum() * costs.verification
    friction_cost = legitimate_challenged * costs.friction
    daily_reviews = review.groupby(actions["day"]).sum()

    return {
        "total_cost": residual + actions_cost + friction_cost,
        "fraud_prevented": prevented,
        "residual_fraud": residual,
        "action_cost": actions_cost,
        "friction_cost": friction_cost,
        "fraud_cases_addressed": int(((review | verify) & fraud).sum()),
        "legit_challenges_per_1000": 1000 * legitimate_challenged / max((~fraud).sum(), 1),
        "reviews": int(review.sum()),
        "reviews_per_day": daily_reviews.mean(),
        "peak_reviews": int(daily_reviews.max()),
        "verifications": int(verify.sum()),
    }


def compare(scored, capacity, review_threshold, verify_threshold, costs):
    return pd.DataFrame([
        {"policy": policy, **evaluate(
            decisions(scored, policy, capacity, review_threshold, verify_threshold), costs
        )}
        for policy in POLICIES
    ]).sort_values("total_cost", ignore_index=True)
