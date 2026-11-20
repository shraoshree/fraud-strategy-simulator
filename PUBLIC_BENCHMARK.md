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

Tiered dollars reduced modeled cost by **42.7%** versus score-only review and by **2,282 currency units** versus probability ranking with the same thresholds. The matched comparison has the same challenge rate because ranking changes which challenged transactions get a review and which get verification. In the synthetic sandbox, the ranking winner changed as capacity tightened. Holdout length, currency, model inputs, thresholds and queue windows differ across the two scenarios. The public data contains no intervention outcomes and its 20-hour holdout provides a narrow test of operational performance.

See [metrics and file digest](results/public_metrics.json) and [all policy scenarios](results/public_policy_comparison.csv).
