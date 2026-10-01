"""Conexiunea la Oracle ADB (schema CRM_DEMO) printr-un pool python-oracledb."""
import os

import oracledb
from flask import g

oracledb.defaults.fetch_decimals = True
_pool = None


def pool():
    global _pool
    if _pool is None:
        wallet = os.environ["WALLET_DIR"]
        _pool = oracledb.create_pool(
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            dsn=os.environ["DB_DSN"],
            config_dir=wallet,
            wallet_location=wallet,
            wallet_password=os.environ.get("WALLET_PASSWORD"),
            min=1, max=4, increment=1,
        )
    return _pool


def conn():
    if "db" not in g:
        g.db = pool().acquire()
    return g.db


def close(_exc=None):
    c = g.pop("db", None)
    if c is not None:
        try:
            c.rollback()
        finally:
            pool().release(c)


def _rows(cur):
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur]


def query(sql, params=None):
    with conn().cursor() as cur:
        cur.execute(sql, params or {})
        return _rows(cur)


def one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


def scalar(sql, params=None):
    with conn().cursor() as cur:
        cur.execute(sql, params or {})
        r = cur.fetchone()
        return r[0] if r else None


def execute(sql, params=None):
    with conn().cursor() as cur:
        cur.execute(sql, params or {})
        return cur.rowcount


def commit():
    conn().commit()
