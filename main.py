# main.py
import streamlit as st
from modules.scraper import (
    StockScraper, 
    fetch_stock_history, 
    fetch_stock_info, 
    fetch_watchlist_data,
    WATCHLIST_UPDATE_SEC
)
from ui.sidebar import render_sidebar
from ui.dashboard import render_dashboard

# 페이지 기본 설정 (반드시 코드 최상단에 위치)
st.set_page_config(
    page_title="AutoTrade Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS (선택사항: 여백 조정 등)
st.markdown("""
<style>
    /* Metric 컨테이너 스타일 */
    div[data-testid="stMetric"] {
        background-color: #262730; /* 어두운 회색 (Streamlit 기본 다크 테마 색상) */
        border: 1px solid #464b59; /* 테두리 추가 */
        padding: 15px;
        border-radius: 10px;
        color: white; /* 글자색 강제 흰색 */
        
        /* [핵심 수정] 최소 높이를 지정하여 세 박스의 키를 맞춤 */
        min-height: 140px; 
        
        /* (선택사항) 내용물이 세로 중앙에 오게 하려면 아래 주석 해제 */
        /* display: flex; */
        /* flex-direction: column; */
        /* justify-content: center; */
    }
    
    /* 값(Value) 폰트 크기 조정 */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # 1. 사이드바 렌더링 및 설정값 받아오기
    config = render_sidebar()
    ticker = config['ticker']
    period = config['period']
    # session_state에서 직접 가져옴
    watchlist = st.session_state.get('watchlist', [])

    # 2. 메인 타이틀
    st.title("📈 AI Stock Trading Dashboard")

    # [탭 구성] 기능 분리 - 관심 목록 탭 추가
    tab_analysis, tab_portfolio, tab_watchlist = st.tabs(["📊 종목 분석 & 자동매매", "💰 나의 포트폴리오", "📌 관심 종목 목록"])

    # -----------------------------------------------------
    # TAB 1: 종목 분석 및 자동 매매
    # -----------------------------------------------------
    with tab_analysis:
        # 3. 데이터 수집 및 대시보드 표시
        # 앱이 처음 로드되거나 버튼이 눌렸을 때 실행
        if ticker:
            with st.spinner('데이터를 불러오는 중입니다...'):
                # (1) 주가 데이터 (캐싱 적용)
                df = fetch_stock_history(ticker, period)
                
                # (2) 기본 정보 (캐싱 적용)
                info = fetch_stock_info(ticker)
                
                # (3) 뉴스 (캐싱 미적용 - 최신성 유지)
                scraper = StockScraper(ticker)
                news = scraper.get_news()

            # 데이터가 유효하면 대시보드 그리기
            if info and not df.empty:
                render_dashboard(df, info, news)
            else:
                st.error("데이터를 찾을 수 없습니다. 종목 코드를 확인해주세요.")
        pass

    # -----------------------------------------------------
    # TAB 2: 포트폴리오 관리
    # -----------------------------------------------------
    with tab_portfolio:
        # ... (기존 포트폴리오 관리 로직 유지) ...
        pass

    # -----------------------------------------------------
    # TAB 3: 관심 종목 목록
    # -----------------------------------------------------
    with tab_watchlist:
        st.header("📌 내 관심 종목 현황")
        if watchlist:
            with st.spinner("관심 종목의 최신 주가 정보를 불러오는 중입니다..."):
                watchlist_df = fetch_watchlist_data(watchlist)
            
            if not watchlist_df.empty:
                st.dataframe(
                    watchlist_df.style.format({
                        "현재가": "{:,.2f}",
                        "시가총액": "{:,.0f}"
                    }),
                    use_container_width=True,
                    height=350
                )
                
                st.caption(f"총 {len(watchlist)}개 종목이 등록되어 있습니다. (데이터는 {WATCHLIST_UPDATE_SEC}초마다 갱신됩니다.)")
            else:
                st.error("관심 종목 데이터를 불러오는 데 실패했습니다. 종목 코드를 확인해주세요.")
        else:
            st.info("사이드바에서 종목 코드를 입력하고 '➕ 관심 종목 등록' 버튼을 눌러 목록에 추가해주세요.")


if __name__ == "__main__":
    main()