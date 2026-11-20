SELECT transactions.*,
       CASE WHEN strftime('%H', occurred_at) IN ('00','01','02','03','04','05')
            THEN 1 ELSE 0 END AS overnight,
       (SELECT count(*)
          FROM transactions AS previous
         WHERE previous.card_id = transactions.card_id
           AND previous.occurred_at >= datetime(transactions.occurred_at, '-1 hour')
           AND previous.occurred_at < transactions.occurred_at) AS prior_hour_count
FROM transactions
ORDER BY occurred_at, transaction_id;
