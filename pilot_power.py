"""Plan an equally allocated pilot powered on fraud loss basis points."""

from math import ceil
from statistics import NormalDist


def sample_size_per_arm(mean_spend, residual_sd, detectable_bps, alpha=0.05, power=0.80):
    """Use card-level residual SD from shadow data for the ratio outcome.

    A residual is net fraud loss minus baseline loss per dollar times spend,
    computed per randomized card over the planned measurement window.
    """
    if min(mean_spend, residual_sd, detectable_bps) <= 0:
        raise ValueError("Spend, residual standard deviation, and effect size must be positive.")
    if not 0 < alpha < 1 or not 0.5 < power < 1:
        raise ValueError("Use alpha in (0, 1) and power in (0.5, 1).")
    normal = NormalDist()
    critical = normal.inv_cdf(1 - alpha / 2)
    detectable_dollars = mean_spend * detectable_bps / 10_000
    return ceil(2 * ((critical + normal.inv_cdf(power)) * residual_sd / detectable_dollars) ** 2)


if __name__ == "__main__":
    print(f"{sample_size_per_arm(500, 5, 2):,} eligible cards per arm (illustrative)")
