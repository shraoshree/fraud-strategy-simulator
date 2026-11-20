import unittest

import pandas as pd

from pipeline import sql_analysis
from policy import Costs, decisions, evaluate


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.scored = pd.DataFrame({
            "transaction_id": [1, 2, 3],
            "day": ["2025-03-07", "2025-03-07", "2025-03-08"],
            "risk": [0.8, 0.6, 0.9],
            "amount": [10, 100, 20],
            "is_fraud": [0, 1, 1],
            "channel": ["online"] * 3,
            "prior_hour_count": [0] * 3,
        })

    def test_ranking_and_daily_capacity(self):
        probability = decisions(self.scored, "Tiered probability", 1, 0.5, 0.2)
        dollars = decisions(self.scored, "Tiered dollars", 1, 0.5, 0.2)
        self.assertEqual(list(probability.action), ["review", "verify", "review"])
        self.assertEqual(list(dollars.action), ["verify", "review", "review"])
        self.assertEqual(evaluate(dollars, Costs())["peak_reviews"], 1)

    def test_zero_capacity_preserves_verification(self):
        tiered = decisions(self.scored, "Tiered dollars", 0, 0.5, 0.2)
        threshold = decisions(self.scored, "Score threshold", 0, 0.5, 0.2)
        self.assertEqual(list(tiered.action), ["verify"] * 3)
        self.assertEqual(list(threshold.action), ["approve"] * 3)
        self.assertAlmostEqual(evaluate(tiered, Costs())["total_cost"], 46.25)

    def test_sql_excludes_current_timestamp_and_other_cards(self):
        rows = self.scored.drop(columns=["day", "risk", "prior_hour_count"]).assign(
            card_id=[1, 1, 2], merchant_category="other",
            occurred_at=["2025-03-07 10:00:00", "2025-03-07 11:00:00", "2025-03-07 11:00:00"],
        )
        features, segments = sql_analysis(rows)
        self.assertEqual(list(features.prior_hour_count), [0, 1, 0])
        self.assertEqual(segments.fraud_dollars.sum(), 120)
