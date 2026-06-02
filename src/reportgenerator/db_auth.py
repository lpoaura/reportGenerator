#!/bin/python3

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


@contextmanager
def get_connection(service_name: str):
    """
    Connexion PostgreSQL via pg_service.conf
    """
    with psycopg.connect(service=service_name, row_factory=dict_row) as conn:
        yield conn
