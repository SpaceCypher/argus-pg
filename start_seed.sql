CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE TABLE IF NOT EXISTS users (
    id serial PRIMARY KEY,
    email text,
    created_at timestamp DEFAULT now()
);

INSERT INTO users (email, created_at)
SELECT 
    'user_' || i || '@example.com', 
    now() - (i * interval '1 minute')
FROM generate_series(1, 50000) AS i;
