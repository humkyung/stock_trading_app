# ui/watchlist_ui.py
import streamlit as st

from modules.db import load_watchlist, add_watchlist, remove_watchlist
from modules.scraper import fetch_stock_info
from modules.constants import (
    SK_WATCHLIST,
    SK_NEW_TICKER_INPUT,
    SK_LAST_SELECTED_TICKER,
)


def render_watchlist_section(user_id: str, selected_ticker: str):
    """사이드바에 관심 종목 관리 UI를 렌더링합니다."""
    st.sidebar.subheader("📌 관심 종목 목록")

    # 초기화 및 DB 로딩 (세션에 없을 때만)
    if SK_WATCHLIST not in st.session_state:
        st.session_state[SK_WATCHLIST] = load_watchlist(user_id)

    # 선택된 티커가 바뀌었을 때만 입력창을 자동 업데이트
    if st.session_state.get(SK_LAST_SELECTED_TICKER) != selected_ticker.upper():
        st.session_state[SK_NEW_TICKER_INPUT] = selected_ticker.upper()
        st.session_state[SK_LAST_SELECTED_TICKER] = selected_ticker.upper()

    new_ticker = st.sidebar.text_input("목록에 추가할 종목", key=SK_NEW_TICKER_INPUT)

    # 추가 버튼
    if st.sidebar.button("➕ 관심 종목 등록"):
        if new_ticker:
            ticker_to_add = new_ticker.upper()
            if ticker_to_add not in st.session_state[SK_WATCHLIST]:
                info = fetch_stock_info(new_ticker)
                add_watchlist(user_id, new_ticker, info["name"])
                st.session_state[SK_WATCHLIST] = load_watchlist(user_id)
                st.sidebar.success(f"{ticker_to_add} 등록 완료!")
                st.rerun()
            else:
                st.sidebar.warning("이미 등록된 종목입니다.")

    # 등록된 종목 목록 표시
    if st.session_state[SK_WATCHLIST]:
        st.sidebar.caption("현재 목록:")
        for item in st.session_state[SK_WATCHLIST]:
            ticker = item["ticker"]
            name = item["name"]
            cols = st.sidebar.columns([3, 1])
            cols[0].write(f"- {ticker} ({name})")
            if cols[1].button("❌", key=f"remove_{ticker}"):
                remove_watchlist(user_id, ticker)
                st.session_state[SK_WATCHLIST] = load_watchlist(user_id)
                st.rerun()
