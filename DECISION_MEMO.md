# Fraud policy decision memo

## Recommendation

Advance score-plus-verification to shadow evaluation. At 100 review slots, both tiered strategies produce the same actions and have an estimated cost of $30,836 versus $32,169 for score-only review. The paired 95% bootstrap range for savings crosses zero, and tiered verification adds about 6.08 legitimate challenges per 1,000. Measure verification effectiveness and customer friction before drawing a rollout conclusion.

With the action thresholds fixed, the 100-slot cost crossover is $3.44 per legitimate challenge. At 10 and 15 slots, dollar ranking has a small simulated cost advantage. At 20 and 25 slots, probability ranking leads by $54 and $31. Start the pilot with probability ranking and measure the effect of verification against a score-only control.

## Pilot design

Randomize eligible card accounts 1:1 so repeat purchases from a card stay in one arm. Compare score-only against score-plus-verification, run in parallel, and reserve separate review capacity by arm. The **primary outcome is net confirmed fraud losses in basis points of settled eligible purchase spend**, measured after a predeclared 60-day maturation window. Calculate it as 10,000 × net confirmed fraud loss dollars ÷ settled purchase dollars, separately for each arm. Use a consistent recovery cutoff. Report net loss dollars and settled spend separately so changes in approvals or abandonment are visible. Track fraud attempts as a diagnostic.

For planning, an illustrative two-sided 5% test with 80% power to detect a **2 basis point** difference needs **39,245 eligible cards per arm** if average settled spend is $500 per card and the card-level residual standard deviation is $5. The residual is each card's loss minus its spend multiplied by the baseline loss per dollar. Estimate both inputs from shadow data using the planned eligibility, enrollment and maturity windows. Use card-level randomization and card-level uncertainty for the loss-to-spend ratio. Run `python pilot_power.py` to reproduce the illustrative estimate and re-power before launch.

| Guardrail | Proposed stop limit vs. control |
|---|---|
| Approval rate | Drop greater than 0.5 percentage points |
| Purchase abandonment among eligible transactions | Increase greater than 0.5 percentage points |
| Fraud-policy complaints | Increase greater than 2 per 10,000 eligible transactions |
| Manual-review queue | Reserved capacity exceeded or agreed service window missed on two consecutive days |

Freeze these example limits and their denominators before randomization. Review operational guardrails daily. Pause exposure immediately on a verified severe incident, or when a guardrail exceeds its limit for two consecutive daily checks and both arms have at least 10,000 cumulative eligible transactions. Investigate before restarting. Assess efficacy once the powered sample is reached and labels mature. End the pilot at the preset maximum duration if enrollment falls short and label the efficacy result inconclusive. Predeclare the duration based on shadow traffic. Launch only if the primary effect supports improvement and guardrails remain within their limits.
