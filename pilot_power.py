"""Per-arm normal approximation for a two-sided comparison of proportions."""

from math import ceil, sqrt
from statistics import NormalDist


def sample_size_per_arm(control_rate, treatment_rate, alpha=0.05, power=0.80):
    pooled = (control_rate + treatment_rate) / 2
    critical = NormalDist().inv_cdf(1 - alpha / 2)
    power_z = NormalDist().inv_cdf(power)
    null_sd = sqrt(2 * pooled * (1 - pooled))
    alternative_sd = sqrt(
        control_rate * (1 - control_rate) + treatment_rate * (1 - treatment_rate)
    )
    return ceil(((critical * null_sd + power_z * alternative_sd)
                 / abs(control_rate - treatment_rate)) ** 2)


if __name__ == "__main__":
    print(f"{sample_size_per_arm(0.001, 0.0008):,} transactions per arm before design effect")
