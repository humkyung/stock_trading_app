#main.py
import streamlit as st
from modules.scraper import StockScraper, fetch_stock_history, fetch_stock_info

st.set_page_config(page_title="자동 주식 매매 봇", layout="wide")

st.title("📈 주식 데이터 대시보드")

# 1. 사이드바 입력
st.sidebar.header("설정")
ticker = st.sidebar.text_input("종목 코드 (예: AAPL, 005930.KS)", "AAPL")
period = st.sidebar.selectbox("기간", ["1d", "5d", "1mo", "6mo", "1y", "max"], index=2)

if st.sidebar.button("데이터 조회"):
    # 모듈을 통해 데이터 가져오기
    scraper = StockScraper(ticker)
    
    # 기본 정보 탭과 차트 탭 분리
    tab1, tab2, tab3 = st.tabs(["📊 차트", "ℹ️ 기업 정보", "📰 뉴스"])
    
    with tab1:
        # 캐싱된 함수 사용
        df = fetch_stock_history(ticker, period)
        if not df.empty:
            st.line_chart(df['Close'])
            st.dataframe(df.sort_index(ascending=False).head())
        else:
            st.error("데이터를 가져올 수 없습니다. 종목 코드를 확인하세요.")

    with tab2:
        info = fetch_stock_info(ticker)
        if info:
            col1, col2 = st.columns(2)
            col1.metric("기업명", info['name'])
            col1.metric("시가총액", f"{info['market_cap']:,}")
            col2.metric("PER", info['per'])
            col2.metric("EPS", info['eps'])
            st.caption(info['summary'])
    
    with tab3:
        news_list = scraper.get_news()
        for news in news_list:
            st.markdown(f"**[{news['title']}]({news['link']})**")
            st.caption(f"제공: {news['publisher']}")
            st.write("---")
