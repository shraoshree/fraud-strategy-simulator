# Credit Card Fraud Strategy Simulator

[Open the live dashboard](https://shraoshree-fraud-strategy.streamlit.app/)

## Public-data benchmark

On the public ULB credit card dataset, the 20-hour holdout contained **130,863 transactions and 159 labeled fraud cases**. At **five reviews per hour**, tiered dollar ranking had **42.7% lower modeled cost** than score-only review and saved **2,282 currency units** over probability ranking with matched thresholds and the same challenge rate. The source provides fraud labels. Intervention costs and effectiveness still come from the simulator assumptions.

[Read the dataset source, chronological split, and reproducibility steps](PUBLIC_BENCHMARK.md). The live dashboard opens on the public benchmark and offers the original synthetic sandbox as a separate view.

## Synthetic policy sandbox

**Verification drives the savings. Pilot it to measure whether the value of avoided fraud justifies the customer friction.** In the 100-slot reference scenario, the break-even cost is **$3.44 per legitimate challenge**.

At the $2 baseline, tiered verification saves an estimated **$1,332** over score-only review and raises legitimate challenges from **2.47 to 8.56 per 1,000**. The paired 95% bootstrap interval is **−$59 to $2,805**. Both rankings produce the same actions in this reference scenario because eligible reviews peak at 39 per day.

![Estimated cost versus legitimate challenges at several daily review capacities](results/friction_tradeoff.png)

The synthetic holdout contains **226 fraud cases in 152,259 transactions (0.148%)**. The generator targets a low-prevalence scenario and increases the incident rate in the holdout. These are scenario assumptions. Actual incidence, verification yield, and friction tolerance depend on the portfolio.

## Run the dashboard

Use Python 3.11 or 3.12.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app uses committed aggregate scenario results and starts without model training or credentials. To regenerate the results from the fixed seed, run `python pipeline.py`. Run the tests with `python -m unittest discover -s tests -v`.

## Follow the analysis

| Step | Files | What to look for |
|---|---|---|
| Generate data | [pipeline.py](pipeline.py) | 90 days of transactions, low fraud incidence and a shift on day 66. |
| Build SQL features | [features.sql](sql/features.sql) | Prior-hour activity, spend relative to a 30-day card average, time since the previous transaction and first observed category. Same-second events are excluded from history. |
| Compare models | [model results](results/model_comparison.csv), [calibration](results/calibration.csv) | Days 1–30 warm up history, 31–50 train, 51–65 select model and thresholds, and 66–90 evaluate. Logistic regression won on validation average precision. |
| Compare policies | [policy.py](policy.py), [policy results](results/policy_comparison.csv), [bootstrap](results/bootstrap.csv) | Each model-based policy tunes its thresholds independently on validation. Tiered probability is the score-plus-verification baseline. A matched-threshold comparison isolates the effect of ranking. |
| Monitor outcomes | [monitoring.sql](sql/monitoring.sql), [daily results](results/daily_monitoring.csv) | Track review and verification volume, alert precision and legitimate challenge rate after fraud labels mature. |
| Plan a pilot | [Decision memo](DECISION_MEMO.md), [sample-size calculator](pilot_power.py) | Set guardrails, sample size and stopping rules before launch. |

### What changes when capacity actually binds

Each limit below is reached on at least one day for both tiered policies. Thresholds stay fixed so the comparison isolates the effect of changing review capacity. The ranking winner changes across limits. Every paired 95% interval includes zero, so the holdout gives no clear evidence that one ranking consistently saves more.

| Daily review slots | Average daily reviews | Estimated savings from dollar ranking | Paired 95% interval |
|---:|---:|---:|---:|
| 10 | 9.80 | $55 | −$166 to $333 |
| 15 | 13.84 | $192 | −$153 to $600 |
| 20 | 16.56 | −$54 | −$120 to $0 |
| 25 | 17.48 | −$31 | −$93 to $0 |

Savings are probability-ranking cost minus dollar-ranking cost. The synthetic dashboard view opens at 25 daily slots and lets you explore 0–50. The 100-slot reference remains in the published results.

[View estimated cost by review capacity](results/capacity.png).

### Calibration under drift

In the highest-scoring logistic regression decile, mean prediction and observed fraud moved from **0.68% vs. 0.71%** in validation to **0.76% vs. 1.14%** in holdout. Holdout average precision was **0.167** for logistic regression and **0.054** for histogram gradient boosting, up from 0.019 before regularization. The boosted model used a 0.05 learning rate, larger minimum leaves, and L2 regularization. The best tree size and iteration budget were selected from three configurations on validation average precision. Training contained 118 positives, which limits the evidence for rare-event tree splits. [See the tuning results](results/metrics.json). The deciles are formed independently in each split. The divergence matters because dollar ranking multiplies risk by transaction amount.

### Cost and uncertainty

Total cost adds remaining fraud exposure, action costs, and assumed friction costs. The $3.44 crossover holds the action thresholds and all other assumptions fixed. Review and verification are assumed to prevent 90% and 65% of associated fraud dollars, respectively. The paired bootstrap resamples the same 25 holdout days for every policy and reports 10,000 replicates. Its intervals reflect day-to-day variability in this scenario and leave uncertainty in the synthetic generator and intervention assumptions outside the estimate. The queue is ranked in daily batches.
