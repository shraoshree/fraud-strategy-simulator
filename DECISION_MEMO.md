# Fraud policy decision memo

## Recommendation

Advance score-plus-verification to shadow evaluation. At 100 review slots, both tiered strategies produce the same actions and have an estimated cost of $30,836 versus $32,169 for score-only review. The paired 95% bootstrap range for savings crosses zero, and tiered verification adds about 6.08 legitimate challenges per 1,000. Measure verification effectiveness and customer friction before drawing a rollout conclusion.

At fixed action thresholds, the cost crossover is $3.44 per legitimate challenge. Both tiered policies are cheaper below that assumption, and score-only is cheaper above it. At 25 slots, probability ranking slightly outperformed dollar ranking. Start the pilot with probability ranking and reserve dollar ranking for evaluation if the queue binds and calibration is adequate.

## Pilot design

Randomize eligible card accounts 1:1 so repeat purchases from a card stay in one arm. Compare score-only against score-plus-verification, run in parallel, and reserve separate review capacity by arm. Measure confirmed fraud incidence after a predeclared 60-day label maturation window. Report prevented fraud dollars and total estimated cost separately. Match the experiment eligibility definition to the denominator used in power estimates.

For planning, a two-sided 5% test with 80% power needs **352,881 eligible transactions per arm** to detect a drop from 0.10% to 0.08% under independent observations. If the mean is five eligible transactions per card and within-card correlation is 0.02, the illustrative design effect is 1.08, or **381,112 per arm**. Estimate the design effect from shadow data and re-power if the eligible population's fraud rate differs. Use card-clustered analysis and allow for label delays and incomplete follow-up. Run `python pilot_power.py` to reproduce the unadjusted estimate.

| Guardrail | Proposed stop limit vs. control |
|---|---|
| Approval rate | Drop greater than 0.5 percentage points |
| Purchase abandonment among eligible transactions | Increase greater than 0.5 percentage points |
| Fraud-policy complaints | Increase greater than 2 per 10,000 eligible transactions |
| Manual-review queue | Reserved capacity exceeded or agreed service window missed on two consecutive days |

Freeze these example limits and their denominators before randomization. Review operational guardrails daily. Pause exposure immediately on a verified severe incident, or when a guardrail exceeds its limit for two consecutive daily checks and both arms have at least 10,000 cumulative eligible transactions. Investigate before restarting. Assess efficacy once the powered sample is reached and labels mature. End the pilot at the preset maximum duration if enrollment falls short and label the efficacy result inconclusive. Predeclare the duration based on shadow traffic. Launch only if the primary effect supports improvement and guardrails remain within their limits.
