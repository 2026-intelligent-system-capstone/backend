SELECT 'CREATE DATABASE dev_db'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'dev_db'
)\gexec

SELECT 'CREATE DATABASE test_db'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'test_db'
)\gexec
