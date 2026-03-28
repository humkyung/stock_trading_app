# main.py
import os
import time
import json
from streamlit_cookies_manager import EncryptedCookieManager
from streamlit.errors import StreamlitSecretNotFoundError
import streamlit as st
from modules.scraper import (
    StockScraper,
    fetch_stock_history,
    fetch_stock_info,
    fetch_watchlist_data,
    WATCHLIST_UPDATE_SEC,
)
from ui.sidebar import render_sidebar
from ui.dashboard import render_dashboard
from modules.auth_manager import AuthManager
from ui.login_page import render_login_page
from modules.db import ensure_schema
from modules.trader import KisTrader
from dotenv import load_dotenv

load_dotenv()

# 페이지 기본 설정
st.set_page_config(
    page_title="AutoTrade Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 커스텀 CSS (선택사항: 여백 조정 등)
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)


# 1. Trader 객체 캐싱 (앱 실행 중 1회만 로그인)
@st.cache_resource
def get_trader():
    return KisTrader()


# 2. 세션 상태 초기화 (중복 주문 방지용)
if "bought_status" not in st.session_state:
    st.session_state["bought_status"] = {}  # {ticker: True/False}


def main():
    def get_secret(key: str, default=None):
        try:
            if key in st.secrets:
                return st.secrets.get(key, default)
        except StreamlitSecretNotFoundError:
            pass

        return os.getenv(key, default)

    # --- 쿠키 매니저 (반드시 초반) ---
    password = get_secret("COOKIES_PASSWORD")
    if not password:
        st.error("❌ COOKIES_PASSWORD가 설정되지 않았습니다. 관리자에게 문의하세요.")
        st.stop()

    cookies = EncryptedCookieManager(
        prefix="stock-trading-app/", password=password  # 앱 고유 prefix
    )

    if not cookies.ready():
        st.stop()  # 쿠키 컴포넌트 준비될 때까지 대기

    # -----------------------------------------------------
    # 로그인 세션 관리
    # -----------------------------------------------------
    if "user_info" not in st.session_state:
        st.session_state["user_info"] = None

    # --- ✅ 새로고침(F5) 후에도 쿠키에서 로그인 복원 ---
    if st.session_state["user_info"] is None and cookies.get("user_info"):
        try:
            st.session_state["user_info"] = json.loads(cookies["user_info"])
        except Exception:
            # 쿠키가 깨졌거나 형식이 이상하면 지움
            del cookies["user_info"]
            cookies.save()

    auth_manager = AuthManager()

    # URL 쿼리 파라미터 확인 (로그인 후 리다이렉트 되었을 때)
    # Streamlit 최신 버전은 st.query_params 사용
    query_params = st.query_params

    # 로그인 처리 로직
    if st.session_state["user_info"] is None:
        # A. Google 로그인 콜백
        if (
            "code" in query_params and "state" not in query_params
        ):  # Google은 state 필수가 아님(설정 안했을 시)
            code = query_params["code"]
            user_info = auth_manager.authenticate_google(code)
            if user_info:
                st.session_state["user_info"] = user_info
                # 쿠키에도 저장
                cookies["user_info"] = json.dumps(user_info, ensure_ascii=False)
                cookies.save()
                st.query_params.clear()  # URL 파라미터 청소
                st.rerun()  # 새로고침

        # B. Naver 로그인 콜백
        elif "code" in query_params and "state" in query_params:
            code = query_params["code"]
            state = query_params["state"]
            user_info = auth_manager.authenticate_naver(code, state)
            if user_info:
                st.session_state["user_info"] = user_info
                # 쿠키에도 저장
                cookies["user_info"] = json.dumps(user_info, ensure_ascii=False)
                cookies.save()
                st.query_params.clear()
                st.rerun()

        # C. 로그인 화면 표시
        render_login_page(auth_manager)
        return  # 메인 앱 실행 중단

    # -----------------------------------------------------
    # 메인 앱 실행 (로그인 성공 시)
    # -----------------------------------------------------
    user = st.session_state["user_info"]

    # 사이드바에 사용자 정보 표시
    with st.sidebar:
        st.write(f"👋 환영합니다, **{user.get('name', 'User')}**님!")
        if st.button("로그아웃"):
            st.session_state["user_info"] = None
            # 쿠키에서도 삭제
            if cookies.get("user_info"):
                del cookies["user_info"]
                cookies.save()
            st.rerun()
        st.divider()

    # --- DB 스키마 보장 ---
    ensure_schema()

    # 사이드바 렌더링 및 설정값 받아오기
    config = render_sidebar()
    ticker = config["ticker"]
    period = config["period"]
    is_auto = config["is_auto"]
    # 목표가 설정값 가져오기 (sidebar.py에서 반환값에 추가되어야 함)
    # ※ ui/sidebar.py의 return 딕셔너리에 target_buy, target_sell을 추가했다고 가정
    # 수정된 sidebar.py 코드는 아래 '참고' 섹션 확인
    target_buy = st.session_state.get("target_buy", 0)
    target_sell = st.session_state.get("target_sell", 0)

    # session_state에서 직접 가져옴
    watchlist = st.session_state.get("watchlist", [])

    # 2. 메인 타이틀
    st.title("📈 AI Stock Trading Dashboard")

    # [탭 구성] 기능 분리 - 관심 목록 탭 추가
    tab_analysis, tab_portfolio, tab_watchlist = st.tabs(
        ["📊 종목 분석 & 자동매매", "💰 나의 포트폴리오", "📌 관심 종목 목록"]
    )

    # -----------------------------------------------------
    # TAB 1: 종목 분석 및 자동 매매
    # -----------------------------------------------------
    with tab_analysis:
        # 3. 데이터 수집 및 대시보드 표시
        # 앱이 처음 로드되거나 버튼이 눌렸을 때 실행
        if ticker:
            with st.spinner("데이터를 불러오는 중입니다..."):
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
                current_price = df["Close"].iloc[-1]
            else:
                st.error("데이터를 찾을 수 없습니다. 종목 코드를 확인해주세요.")
            # ---------------------------------------------------------
            # [핵심] 자동 매매 로직 연결
            # ---------------------------------------------------------
            if is_auto:
                st.divider()
                st.subheader("🤖 자동 매매 모니터링")

                status_cols = st.columns(4)
                status_cols[0].metric("현재가", f"{current_price:,.0f}")
                status_cols[1].metric("목표 매수가", f"{config['target_buy']:,.0f}")
                status_cols[2].metric("목표 매도가", f"{config['target_sell']:,.0f}")

                # 로그 창 (컨테이너)
                log_container = st.empty()

                trader = get_trader()

                # 매수 로직
                # 1. 목표가가 설정되어 있고
                # 2. 현재가가 목표가보다 낮거나 같으며
                # 3. 아직 매수하지 않은 상태일 때
                if config["target_buy"] > 0 and current_price <= config["target_buy"]:
                    if not st.session_state["bought_status"].get(ticker, False):
                        log_container.warning(
                            f"⚡ 매수 조건 충족! ({current_price} <= {config['target_buy']}) 주문 실행 중..."
                        )

                        # API 주문 실행 (수량 1주로 고정 예시)
                        success = trader.send_order(ticker, 1, 0, "buy")

                        if success:
                            st.session_state["bought_status"][ticker] = True
                            st.success(f"✅ {ticker} 1주 매수 완료!")
                            time.sleep(1)  # 메시지 확인용 대기
                        else:
                            st.error("❌ 매수 주문 실패")
                    else:
                        status_cols[3].info("상태: 이미 매수함")

                # 매도 로직
                elif (
                    config["target_sell"] > 0 and current_price >= config["target_sell"]
                ):
                    if st.session_state["bought_status"].get(ticker, False):
                        log_container.warning(
                            f"⚡ 매도 조건 충족! ({current_price} >= {config['target_sell']}) 주문 실행 중..."
                        )

                        success = trader.send_order(ticker, 1, 0, "sell")

                        if success:
                            st.session_state["bought_status"][
                                ticker
                            ] = False  # 매도했으므로 상태 초기화
                            st.success(f"✅ {ticker} 1주 매도 완료!")
                            time.sleep(1)
                        else:
                            st.error("❌ 매도 주문 실패")
                    else:
                        status_cols[3].info("상태: 보유 주식 없음")

                else:
                    log_container.info("⏳ 조건 감시 중... (특이사항 없음)")

                # 자동 리프레시 (3초마다 재실행하여 실시간 감시 효과)
                time.sleep(3)
                st.rerun()

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
                    watchlist_df.style.format(
                        {"현재가": "{:,.2f}", "시가총액": "{:,.0f}"}
                    ),
                    use_container_width=True,
                    height=350,
                )

                st.caption(
                    f"총 {len(watchlist)}개 종목이 등록되어 있습니다. (데이터는 {WATCHLIST_UPDATE_SEC}초마다 갱신됩니다.)"
                )
            else:
                st.error(
                    "관심 종목 데이터를 불러오는 데 실패했습니다. 종목 코드를 확인해주세요."
                )
        else:
            st.info(
                "사이드바에서 종목 코드를 입력하고 '➕ 관심 종목 등록' 버튼을 눌러 목록에 추가해주세요."
            )


if __name__ == "__main__":
    main()
