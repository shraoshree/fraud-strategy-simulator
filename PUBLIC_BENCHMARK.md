# Public benchmark on ULB credit card transactions

The [ULB Machine Learning Group dataset](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) contains 284,807 anonymized transactions from European cardholders over two days in September 2013. It includes 492 labeled fraud cases, elapsed time, transaction amount and 28 precomputed PCA features.

## Reproduce the run

Download `creditcard.csv` from the source or the [TensorFlow tutorial mirror](https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv). Keep the original CSV under the ignored `data/` directory and run:

```sh
python public_benchmark.py data/creditcard.csv
```

The script records the input SHA-256 and writes aggregate results. The repository and live app use these aggregates.

## Evaluation design

| Elapsed hours | Use | Transactions | Fraud cases |
|---|---|---:|---:|
| 0–19 | Fit standardization and logistic regression | 110,852 | 239 |
| 20–27 | Tune action thresholds at five hourly review slots | 43,092 | 94 |
| 28–47 | Evaluate the fixed thresholds and multiple review capacities | 130,863 | 159 |

The model uses V1–V28 and log amount. Time controls the split and queue grouping. Holdout average precision was **0.550** at a **0.1215%** fraud rate. The published PCA transformation was fit upstream and its fitting window is unavailable. Card identifiers, merchant categories and channels are unavailable, so the benchmark omits the sandbox's card-history features and rules baseline.

The simulator applies 2, 5, 10 and 15 reviews per elapsed hour. Review queues are ranked after each hour's eligible transactions are available. Where ranking is compared directly, both tiered policies use the same thresholds and action options. As in the sandbox, intervention costs, friction, and effectiveness are scenario inputs. Benchmark costs use the same currency units as the dataset amounts.

## Results at five reviews per hour

| Policy | Estimated cost | Legitimate challenges per 1,000 |
|---|---:|---:|
| Score threshold | 18,881 | 0.31 |
| Tiered probability | 13,092 | 1.01 |
| Tiered dollars | 10,826 | 1.01 |
| Matched probability | 13,108 | 1.01 |

The model ranked labeled fraud on a later holdout, and peak reviews stayed within all four tested hourly limits. At five reviews per hour, each matched tiered policy challenged the same 111 labeled fraud cases and 132 legitimate transactions. Dollar ranking routed more of the observed fraud amount into manual review: 12,988 currency units versus 3,861 for probability ranking.

Under 65% assumed verification effectiveness, tiered dollar ranking cost **42.7% less in the model** than score-only review. The comparison changes both the action set and the ranking. Adding verification to the same probability-ranked review queue cuts modeled cost by **5,773 currency units**. Changing to dollar ranking at those same tiered thresholds cuts a further **2,282 units**. Those effects depend on the order of the comparison. Dollar ranking leaves only 214 units of labeled fraud amount in the verification tier, so reducing verification effectiveness to zero adds only **139 units** to that policy's modeled cost with routing and other assumptions fixed.

The **rough paired 95% bootstrap interval** for the matched ranking savings is **1,122 to 3,580 currency units**. It uses 10,000 draws of the 20 paired hourly blocks, with each hour's outcomes held together across the policies. The interval treats hours as exchangeable and holds the fitted model, thresholds and costs fixed. A single 20-hour window provides limited evidence about another portfolio or a longer operating period.

See [metrics, bootstrap results and file digest](results/public_metrics.json) and [all policy scenarios](results/public_policy_comparison.csv).
