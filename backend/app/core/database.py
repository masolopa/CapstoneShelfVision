"""Conexiones cortas con commit/rollback y consultas parametrizadas."""
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row


class Database:
    def __init__(self, conninfo: str):
        self.conninfo = conninfo

    @contextmanager
    def connection(self):
        with psycopg.connect(self.conninfo, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL search_path TO regova, public")
            conn.execute("SET LOCAL statement_timeout = '15s'")
            yield conn
