import unittest

import pandas as pd

from policy import Costs
from public_benchmark import paired_hourly_bootstrap


class PublicBenchmarkTests(unittest.TestCase):
    def test_paired_bootstrap_preserves_hours_and_sign(self):
        probability = pd.DataFrame({
            "day": [28, 28, 29, 29],
            "action": ["approve", "review", "approve", "review"],
            "is_fraud": [1, 1, 1, 1],
            "amount": [80, 40, 60, 20],
        })
        dollars = probability.assign(action=["review", "approve", "review", "approve"])
        # Reordering the probability rows must not change which hours are paired.
        result = paired_hourly_bootstrap(dollars, probability.iloc[::-1], Costs())
        self.assertEqual(result["hour_blocks"], 2)
        for key in ("estimated_savings", "low_95", "high_95"):
            self.assertAlmostEqual(result[key], 72)
