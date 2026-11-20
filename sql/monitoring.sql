SELECT day, policy,
       count(*) AS transactions,
       sum(action = 'review') AS reviews,
       sum(action = 'verify') AS verifications,
       sum(action <> 'approve') AS alerts,
       sum((action <> 'approve') AND is_fraud = 1) AS fraud_alerts,
       1.0 * sum((action <> 'approve') AND is_fraud = 1)
           / NULLIF(sum(action <> 'approve'), 0) AS alert_precision,
       1.0 * sum((action <> 'approve') AND is_fraud = 0)
           / NULLIF(sum(is_fraud = 0), 0) AS legitimate_challenge_rate
FROM policy_actions
GROUP BY day, policy
ORDER BY day, policy;
