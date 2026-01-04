#modules/db.py 
import os
import streamlit as st
import psycopg
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv

load_dotenv()

def get_secret(key: str, default=None):
    try:
        if key in st.secrets:
            return st.secrets.get(key, default)
    except StreamlitSecretNotFoundError:
        pass

    return os.getenv(key, default)

def get_conn():
    return psycopg.connect(
        host=get_secret("PGHOST"),
        port=get_secret("PGPORT", "5432"),
        dbname=get_secret("PGDATABASE"),
        user=get_secret("PGUSER"),
        password=get_secret("PGPASSWORD"),
        connect_timeout=5,
    )

def ensure_schema():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS watchlists (
          user_id TEXT NOT NULL,
          ticker TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, ticker)
        );
        CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists(user_id);
        """)
        conn.commit()

def load_watchlist(user_id: str) -> list[str]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT ticker FROM watchlists WHERE user_id=%s ORDER BY ticker;", (user_id,))
        return [r[0] for r in cur.fetchall()]

def add_watchlist(user_id: str, ticker: str):
    ticker = ticker.upper().strip()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
          INSERT INTO watchlists(user_id, ticker)
          VALUES (%s, %s)
          ON CONFLICT (user_id, ticker) DO NOTHING;
        """, (user_id, ticker))
        conn.commit()

def remove_watchlist(user_id: str, ticker: str):
    ticker = ticker.upper().strip()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM watchlists WHERE user_id=%s AND ticker=%s;", (user_id, ticker))
        conn.commit()