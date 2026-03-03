#!/bin/python3

import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager

@contextmanager
def get_connection(service_name: str):
    """
    Connexion PostgreSQL via pg_service.conf
    """
    with psycopg.connect(service=service_name, row_factory=dict_row) as conn:
        yield conn