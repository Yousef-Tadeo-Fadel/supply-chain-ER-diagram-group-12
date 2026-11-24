import os

import psycopg
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(host=os.environ["DB_HOST"], port=os.getenv("DB_PORT", "5432"),
                           dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
                           password=os.environ["DB_PASSWORD"], connect_timeout=5,
                           options="-c search_path=public -c statement_timeout=8000",
                           row_factory=dict_row)

