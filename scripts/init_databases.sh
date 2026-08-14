#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v retail_db="$RETAIL_DB" \
  -v airflow_db="$AIRFLOW_DB" <<'EOSQL'
SELECT 'CREATE DATABASE ' || quote_ident(:'retail_db')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'retail_db')\gexec

SELECT 'CREATE DATABASE ' || quote_ident(:'airflow_db')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'airflow_db')\gexec
EOSQL
