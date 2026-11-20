# Fraud policy decision memo

## Recommendation

Pilot tiered review prioritized by estimated fraud dollars if verification works well enough and the business can accept roughly 76 challenged legitimate transactions per 1,000. Use score-only review as a fallback when verification produces little benefit or friction exceeds the agreed limit.

| Policy at 100 reviews per day | Estimated 25-day cost | Fraud dollars prevented | Legitimate challenges per 1,000 |
|---|---:|---:|---:|
| Rules only | $201,047 | $311,989 | 29.5 |
| Score threshold | $166,993 | $345,314 | 23.4 |
| Tiered probability | $126,473 | $394,737 | 75.6 |
| Tiered dollars | $122,971 | $398,240 | 75.6 |

The two tiered policies challenged the same set of transactions. Dollar ranking shifted reviews toward higher-dollar exposure and prevented an estimated $3,502 more fraud dollars under the fixed assumptions. The score-only policy challenged fewer legitimate transactions, at an estimated $44,022 higher total cost than tiered dollar ranking.

## What changes the decision

At 100 reviews per day, raising the extra cost per legitimate challenge from $2 to $20 makes score-only review the lowest-cost policy under the other baseline assumptions. Setting verification effectiveness to zero alone narrows the cost advantage over score-only review to about $3,705. Verification can prevent fraud in the simulator because it is assumed to stop a configurable share of associated fraud dollars. A manual review costs $4 and prevents an assumed 90% of associated fraud dollars. Verification costs $0.75 at baseline, and each legitimate challenge adds an assumed $2 of customer friction.

Total cost is residual fraud dollars plus review cost, verification cost, and legitimate challenge cost. Fraud cases addressed counts flagged fraud cases, regardless of whether their associated dollars were prevented.

## Pilot design

Start with shadow scoring to measure queue utilization and challenge volume by channel and merchant category. Use mature fraud labels to measure losses. In a controlled pilot, measure verification completion, legitimate purchase abandonment, handling costs, and prevented fraud dollars. Set a customer friction limit before rollout and track peak queue demand. A real-time authorization workflow would need a queue pacing strategy because the simulation ranks transactions after the full day's candidates are available.

Synthetic data imposes its own relationships between features and fraud. The reported savings measure the behavior of those assumptions. They cannot estimate savings for a real portfolio.
