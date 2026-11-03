"""
Test settings against a real PostgreSQL + PostGIS database.

The default test settings use SQLite, which skips the PostGIS code paths
(radius search, distance sort, geography columns). CI runs the suite a
second time with these settings; set DATABASE_URL to a disposable database
whose template has the postgis extension (see infra/postgres-init).
"""
from .test import *  # noqa

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://rental:rental@localhost:5432/rental_marketplace")}
