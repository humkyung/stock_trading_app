# ui/sidebar.py
import streamlit as st
from datetime import datetime

def render_sidebar():
    """
    사이드바 UI를 렌더링하고 사용자 입력값을 반환합니다.
    """
    st.sidebar.header("⚙️ 시스템 설정")
    
    # 1. 종목 설정 섹션
    st.sidebar.subheader("1. 종목 검색")
    ticker = st.sidebar.text_input("티커 입력 (예: AAPL, NVDA, 005930.KS)", value="AAPL")
    
    # 2. 차트 기간 설정
    period = st.sidebar.selectbox(
        "데이터 기간", 
        ["1d", "5d", "1mo", "3mo", "6mo", "1y", "ytd", "max"], 
        index=2
    )
    
    st.sidebar.markdown("---")
    
    # 3. 자동 매매 조건 (목업)
    st.sidebar.subheader("2. 자동 매매 조건")
    target_buy_price = st.sidebar.number_input("목표 매수가 ($)", min_value=0.0, value=0.0, step=1.0)
    target_sell_price = st.sidebar.number_input("목표 매도가 ($)", min_value=0.0, value=0.0, step=1.0)
    
    is_auto_trading = st.sidebar.toggle("🤖 자동 매매 활성화")
    
    if is_auto_trading:
        st.sidebar.success("자동 매매 감시 중...")
    
    st.sidebar.markdown("---")
    
    # 실행 버튼
    run_btn = st.sidebar.button("데이터 조회 및 적용", type="primary")
    
    return {
        "ticker": ticker.upper(),
        "period": period,
        "run_btn": run_btn,
        "is_auto": is_auto_trading
    }