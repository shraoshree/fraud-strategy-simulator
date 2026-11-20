WITH history AS (
    SELECT *,
           unixepoch(occurred_at) AS event_second,
           count(*) OVER recent AS prior_hour_count,
           avg(amount) OVER monthly AS avg_amount_30d,
           max(unixepoch(occurred_at)) OVER all_prior AS last_event_second,
           count(*) OVER (
               PARTITION BY card_id, merchant_category
               ORDER BY unixepoch(occurred_at)
               RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
           ) AS prior_category_count
    FROM transactions
    WINDOW
        recent AS (PARTITION BY card_id ORDER BY unixepoch(occurred_at)
                   RANGE BETWEEN 3600 PRECEDING AND 1 PRECEDING),
        monthly AS (PARTITION BY card_id ORDER BY unixepoch(occurred_at)
                    RANGE BETWEEN 2592000 PRECEDING AND 1 PRECEDING),
        all_prior AS (PARTITION BY card_id ORDER BY unixepoch(occurred_at)
                      RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
)
SELECT transaction_id, card_id, occurred_at, channel, merchant_category, amount, is_fraud,
       CAST(strftime('%H', occurred_at) AS INTEGER) < 6 AS overnight,
       prior_hour_count, avg_amount_30d,
       amount / NULLIF(avg_amount_30d, 0) AS amount_to_30d_avg,
       event_second - last_event_second AS seconds_since_prior,
       prior_category_count = 0 AS new_category
FROM history
ORDER BY occurred_at, transaction_id;
