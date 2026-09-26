#!/bin/sh
set -eu

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=app_user="$APP_DB_USER" \
  --set=app_password="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE :"app_user" LOGIN NOSUPERUSER CREATEDB PASSWORD :'app_password';
ALTER DATABASE rental_marketplace OWNER TO :"app_user";
SQL

# The application schema uses PostGIS geography and GiST indexes.
psql --username "$POSTGRES_USER" --dbname="$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
  --command='CREATE EXTENSION IF NOT EXISTS postgis;'

# New test databases are cloned from template1, so install PostGIS there too.
psql --username "$POSTGRES_USER" --dbname=template1 --set=ON_ERROR_STOP=1 \
  --command='CREATE EXTENSION IF NOT EXISTS postgis;'
