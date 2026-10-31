"""Connection to the OLTP database (MySQL ecommerce_oltp).

Settings come from environment variables (set in .env / docker-compose.yaml),
so no password is written in the code. Defaults match docker-compose.yaml.
"""
import os

import mysql.connector
from sqlalchemy import create_engine


def mysql_settings():
    return {
        "host": os.getenv("OLTP_HOST", "mysql"),
        "port": int(os.getenv("OLTP_PORT", "3306")),
        "user": os.getenv("OLTP_USER", "oltp_user"),
        "password": os.getenv("OLTP_PASSWORD", "oltp_password"),
        "database": os.getenv("OLTP_DB", "ecommerce_oltp"),
    }


def get_mysql_connection():
    """Plain DB-API connection. Raises an error if the database cannot be reached."""
    return mysql.connector.connect(**mysql_settings())


def get_mysql_engine():
    """SQLAlchemy engine for pandas.read_sql."""
    s = mysql_settings()
    url = f"mysql+mysqlconnector://{s['user']}:{s['password']}@{s['host']}:{s['port']}/{s['database']}"
    return create_engine(url)
