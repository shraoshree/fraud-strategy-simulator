import unittest

import pandas as pd

from pilot_power import sample_size_per_arm
from pipeline import bootstrap, sql_analysis
from policy import Costs


class AnalysisTests(unittest.TestCase):
    def test_card_history_features_exclude_current_and_stale_transactions(self):
        transactions = pd.DataFrame({
            "transaction_id": [1, 2, 3, 4, 5],
            "card_id": [1, 1, 1, 1, 2],
            "occurred_at": ["2025-01-01 10:00:00", "2025-01-02 10:00:00",
                            "2025-02-01 10:00:00", "2025-02-01 10:00:00",
                            "2025-02-01 10:00:00"],
            "channel": ["online"] * 5,
            "merchant_category": ["grocery", "fuel", "grocery", "travel", "grocery"],
            "amount": [100, 20, 60, 40, 500],
            "is_fraud": [0] * 5,
        })
        features, _ = sql_analysis(transactions)
        self.assertEqual(features["new_category"].tolist(), [1, 1, 0, 1, 1])
        self.assertEqual(features.loc[2:3, "avg_amount_30d"].tolist(), [20, 20])
        self.assertEqual(features.loc[2:3, "amount_to_30d_avg"].tolist(), [3, 2])
        self.assertEqual(features.loc[2:3, "seconds_since_prior"].tolist(), [2592000, 2592000])
        self.assertTrue(pd.isna(features.loc[4, "avg_amount_30d"]))

    def test_day_bootstrap_pairs_policies(self):
        approved = pd.DataFrame({
            "day": ["2025-01-01", "2025-01-02"], "is_fraud": [1, 1],
            "amount": [100, 100], "action": ["approve", "approve"],
        })
        verified = approved.assign(action="verify")
        results = bootstrap({
            "Tiered dollars": verified, "Score threshold": approved,
            "Tiered probability": verified, "Matched probability": verified,
        }, Costs()).set_index("comparator")
        self.assertEqual(results.loc["Score threshold"].tolist(), [128.5] * 3)
        self.assertEqual(results.loc["Matched probability"].tolist(), [0] * 3)

    def test_pilot_power_uses_basis_points_and_variance(self):
        self.assertEqual(sample_size_per_arm(500, 5, 2), 39245)
        self.assertEqual(sample_size_per_arm(1000, 5, 1), 39245)
        self.assertGreater(sample_size_per_arm(500, 10, 2), 150_000)
        with self.assertRaises(ValueError):
            sample_size_per_arm(500, 5, 0)
