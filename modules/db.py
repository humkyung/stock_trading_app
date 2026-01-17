# modules/db.py
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
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS watchlists (
          user_id TEXT NOT NULL,
          ticker TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, ticker)
        );
        CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists(user_id);
        """
        )

        # 기존 테이블에 stock_name 컬럼이 없으면 추가 (마이그레이션)
        cur.execute(
            """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='watchlists' AND column_name='stock_name'
            ) THEN
                ALTER TABLE watchlists ADD COLUMN stock_name TEXT;
            END IF;
        END
        $$;
        """
        )

        # 매매일지 테이블
        # user_id와 journal_date를 복합키로 사용하여 유저별로 날짜당 1개의 일지만 존재하도록 함
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS journals (
          user_id TEXT NOT NULL,
          journal_date DATE NOT NULL,
          content TEXT,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, journal_date)
        );
        CREATE INDEX IF NOT EXISTS idx_journals_user_date ON journals(user_id, journal_date);
        """
        )
        conn.commit()


def load_watchlist(user_id: str) -> list[str]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT ticker, stock_name FROM watchlists WHERE user_id=%s ORDER BY ticker;",
            (user_id,),
        )
        rows = cur.fetchall()

        # 딕셔너리 리스트 형태로 변환하여 반환
        result = []
        for r in rows:
            ticker = r[0]
            name = r[1] if r[1] else ticker  # 이름이 없으면 티커로 대체
            result.append({"ticker": ticker, "name": name})

        return result


def add_watchlist(user_id: str, ticker: str, stock_name: str):
    ticker = ticker.upper().strip()
    with get_conn() as conn, conn.cursor() as cur:
        # 이미 존재하면(ON CONFLICT) 이름을 업데이트하도록 설정
        cur.execute(
            """
          INSERT INTO watchlists(user_id, ticker, stock_name)
          VALUES (%s, %s, %s)
          ON CONFLICT (user_id, ticker) DO UPDATE SET stock_name = EXCLUDED.stock_name;
        """,
            (user_id, ticker, stock_name),
        )
        conn.commit()


def remove_watchlist(user_id: str, ticker: str):
    ticker = ticker.upper().strip()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM watchlists WHERE user_id=%s AND ticker=%s;", (user_id, ticker)
        )
        conn.commit()


# 매매 일지 관련 함수
def get_journal_dates(user_id: str) -> list:
    """
    사용자가 일지를 작성한 날짜 목록을 반환합니다.
    달력에 이벤트를 표시하기 위해 사용됩니다.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT journal_date FROM journals 
            WHERE user_id=%s;
        """,
            (user_id,),
        )
        # datetime.date 객체 리스트 반환
        return [row[0] for row in cur.fetchall()]


def save_journal(user_id: str, date, content: str):
    """
    매매 일지 저장 (Upsert: 있으면 업데이트, 없으면 삽입)
    date: datetime.date 객체 또는 'YYYY-MM-DD' 문자열
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
          INSERT INTO journals(user_id, journal_date, content, updated_at)
          VALUES (%s, %s, %s, now())
          ON CONFLICT (user_id, journal_date)
          DO UPDATE SET 
            content = EXCLUDED.content, 
            updated_at = now();
        """,
            (user_id, date, content),
        )
        conn.commit()


def load_journal(user_id: str, date) -> str:
    """
    특정 날짜의 매매 일지 내용을 불러옴
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT content FROM journals 
            WHERE user_id=%s AND journal_date=%s;
        """,
            (user_id, date),
        )
        result = cur.fetchone()
        return result[0] if result else ""
