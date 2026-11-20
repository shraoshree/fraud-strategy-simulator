SELECT channel, merchant_category, count(*) AS transactions,
       sum(is_fraud) AS fraud_cases,
       round(100.0 * avg(is_fraud), 2) AS fraud_rate_pct,
       round(sum(amount * is_fraud), 2) AS fraud_dollars
FROM transactions
GROUP BY channel, merchant_category
ORDER BY fraud_dollars DESC;
