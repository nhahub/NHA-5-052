"""Connection to the data warehouse (PostgreSQL ecommerce_dw).

Settings come from environment variables (set in .env / docker-compose.yaml).
Defaults match docker-compose.yaml.
"""
import os

import psycopg2


def get_postgres_dw_connection():
    """Raises an error if the warehouse cannot be reached (no silent None)."""
    return psycopg2.connect(
        host=os.getenv("DW_HOST", "postgres-dw"),
        port=int(os.getenv("DW_PORT", "5432")),
        user=os.getenv("DW_USER", "dw_user"),
        password=os.getenv("DW_PASSWORD", "dw_password"),
        dbname=os.getenv("DW_DB", "ecommerce_dw"),
    )
