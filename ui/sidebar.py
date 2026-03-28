# ui/sidebar.py
import streamlit as st

from modules.constants import SK_USER_INFO, SK_WATCHLIST
from ui.stock_search import search_assets
from ui.watchlist_ui import render_watchlist_section


def render_sidebar():
    """사이드바 UI를 렌더링하고 사용자 입력값을 반환합니다."""
    st.sidebar.header("⚙️ 시스템 설정")

    # 1. 종목 검색
    st.sidebar.subheader("1. 종목 검색")
    search_query = st.sidebar.text_input(
        "종목명 또는 티커 검색",
        placeholder="(예: 삼성전자, Apple, Nvidia, BTC)",
        help="종목명이나 티커를 입력하여 검색하세요.",
        value="AAPL",
    )

    selected_ticker = search_query.upper()
    if search_query:
        candidates = search_assets(search_query)
        if candidates:
            options = {
                f"{c['symbol']} - {c['name']} ({c['exch']})": c["symbol"]
                for c in candidates
            }
            selection = st.sidebar.selectbox("검색 결과 선택", options.keys(), index=0)
            selected_ticker = options[selection]
        else:
            st.sidebar.warning("검색 결과가 없습니다. 티커를 직접 사용합니다.")
            selected_ticker = search_query.upper()
    else:
        st.sidebar.caption("위 검색창에 종목명을 입력하세요. (기본값: AAPL)")
        selected_ticker = "AAPL"

    st.sidebar.info(f"선택된 티커: **{selected_ticker}**")
    st.sidebar.markdown("---")

    # 2. 관심 종목 관리
    user = st.session_state.get(SK_USER_INFO)
    user_id = user.get("id")
    render_watchlist_section(user_id, selected_ticker)

    st.sidebar.markdown("---")

    # 3. 차트 기간 설정
    period = st.sidebar.selectbox(
        "데이터 기간", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "ytd", "max"], index=2
    )

    st.sidebar.markdown("---")

    # 4. 자동 매매 조건
    st.sidebar.subheader("2. 자동 매매 조건")
    target_buy_price = st.sidebar.number_input(
        "목표 매수가 ($)", min_value=0.0, value=0.0, step=1.0
    )
    target_sell_price = st.sidebar.number_input(
        "목표 매도가 ($)", min_value=0.0, value=0.0, step=1.0
    )

    is_auto_trading = st.sidebar.toggle("🤖 자동 매매 활성화")
    if is_auto_trading:
        st.sidebar.success("자동 매매 감시 중...")

    st.sidebar.markdown("---")

    run_btn = st.sidebar.button("데이터 조회 및 적용", type="primary")

    return {
        "ticker": selected_ticker.upper(),
        "period": period,
        "run_btn": run_btn,
        "is_auto": is_auto_trading,
        "target_buy": target_buy_price,
        "target_sell": target_sell_price,
        "watchlist": st.session_state[SK_WATCHLIST],
    }
