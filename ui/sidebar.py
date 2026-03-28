# ui/sidebar.py
import streamlit as st
import FinanceDataReader as fdr
from datetime import datetime
import requests
import re  # 정규표현식 모듈 추가
import pandas as pd
import os
from modules.db import load_watchlist, add_watchlist, remove_watchlist
from modules.scraper import fetch_stock_info
from modules.constants import (
    SK_USER_INFO,
    SK_WATCHLIST,
    SK_NEW_TICKER_INPUT,
    SK_LAST_SELECTED_TICKER,
)


# -----------------------------------------------------------
# 한국 주식 데이터 로딩 및 검색 (FinanceDataReader)
# -----------------------------------------------------------
@st.cache_data
def get_krx_list():
    """
    한국거래소(KRX) 상장 종목 전체 리스트를 가져와 캐싱합니다.
    서버 실행 시 최초 1회만 실행되므로 속도가 빠릅니다.
    """
    # KRX 전체(코스피, 코스닥, 코넥스) 가져오기
    try:
        df = fdr.StockListing("KRX")
        # 필요한 컬럼만 추출 (Code, Name, Market)
        return df[["Code", "Name", "Market"]]
    except Exception as e:
        st.warning(f"KRX Listing(FDR) 실패 → CSV 백업으로 폴백: {repr(e)}")

        # 백업 CSV (커뮤니티에서 많이 쓰는 미러)
        # 필요하면 이 URL을 네가 관리하는 파일/레포로 바꾸는 걸 추천
        backup_url = "https://raw.githubusercontent.com/corazzon/finance-data-analysis/main/krx.csv"

        try:
            df = pd.read_csv(backup_url)
            # 🔑 컬럼명 표준화 (Symbol → Code)
            if "Symbol" in df.columns and "Code" not in df.columns:
                df = df.rename(columns={"Symbol": "Code"})

            # 백업 파일 컬럼명이 다를 수 있어서 방어적으로 처리
            for col in ["Code", "Name", "Market"]:
                if col not in df.columns:
                    raise ValueError(
                        f"백업 CSV에 {col} 컬럼이 없습니다. columns={df.columns.tolist()}"
                    )
            return df[["Code", "Name", "Market"]]
        except Exception as e2:
            st.error(f"KRX CSV 폴백도 실패: {repr(e2)}")
            return pd.DataFrame()


def search_krx_market(query):
    """
    캐시된 KRX 리스트에서 종목명 또는 코드로 검색합니다.
    """
    df = get_krx_list()

    if df.empty:
        return []

    # 종목명(Name)에 검색어가 포함되어 있거나, 코드(Code)가 일치하는 경우
    # 대소문자 무시 검색은 한글엔 영향 없으나 영어 혼용 시 유용
    mask = df["Name"].str.contains(query, case=False) | df["Code"].str.contains(query)
    results_df = df[mask]

    search_results = []
    # 검색 결과 상위 10개만 리턴
    for _, row in results_df.head(10).iterrows():
        # yfinance 호환을 위해 접미사 추가
        market_suffix = ""
        if row["Market"] in ["KOSPI"]:
            market_suffix = ".KS"
        elif row["Market"] in [
            "KOSDAQ",
            "KONEX",
        ]:  # 코넥스도 보통 KQ로 잡히거나 검색 안될 수 있음
            market_suffix = ".KQ"

        # 접미사가 없으면(Global 등) 일단 KS로 가정하거나 생략
        final_ticker = f"{row['Code']}{market_suffix}"

        search_results.append(
            {
                "symbol": final_ticker,
                "name": row["Name"],
                "exch": row["Market"],
                "type": "Stock (KR)",
            }
        )

    return search_results


# -----------------------------------------------------------
# 미국/코인 데이터 검색 (Yahoo Finance API)
# -----------------------------------------------------------
def search_yahoo_market(query):
    """
    Yahoo Finance API를 이용해 미국 주식, ETF, 코인을 검색합니다.
    """
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            "q": query,
            "quotesCount": 10,
            "newsCount": 0,
            # region을 지정하지 않아야 글로벌(미국 포함) 검색이 원활함
        }
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers, params=params, timeout=3)
        data = response.json()

        results = []
        if "quotes" in data:
            for item in data["quotes"]:
                if "symbol" in item:
                    # 유효한 자산 타입만 필터링 (주식, ETF, 코인)
                    # 옵션 등 복잡한 파생상품 제외 권장
                    results.append(
                        {
                            "symbol": item["symbol"],
                            "name": item.get("shortname")
                            or item.get("longname")
                            or item["symbol"],
                            "exch": item.get("exchange", "Unknown"),
                            "type": item.get("quoteType", "Global"),
                        }
                    )
        return results
    except Exception as e:
        print(f"Yahoo Search Error: {e}")
        return []


def contains_korean(text):
    """문자열에 한글이 포함되어 있는지 확인합니다."""
    korean_pattern = re.compile("[가-힣]")
    return bool(korean_pattern.search(text))


def search_assets(query):
    """
    입력 언어에 따라 검색 엔진을 분기합니다.
    """
    if not query:
        return []

    # 1. 한글이 포함되어 있으면 -> FinanceDataReader (한국 시장)
    if contains_korean(query):
        return search_krx_market(query)

    # 2. 숫자만 6자리(한국 종목코드)인 경우 -> FinanceDataReader
    if query.isdigit() and len(query) == 6:
        return search_krx_market(query)

    # 3. 그 외 (영어, 티커 등) -> Yahoo Finance (미국/코인)
    # 영문으로 된 한국 기업(Samsung)을 찾고 싶을 수도 있으므로
    # Yahoo 결과를 기본으로 하되, 필요하면 KRX 영어명 검색을 추가할 수도 있음.
    # 여기서는 심플하게 영어 -> 해외주식/코인 으로 처리
    return search_yahoo_market(query)


def render_sidebar():
    """
    사이드바 UI를 렌더링하고 사용자 입력값을 반환합니다.
    (이름 기반 검색 기능 추가됨)
    """
    st.sidebar.header("⚙️ 시스템 설정")

    # 1. 종목 설정 섹션
    st.sidebar.subheader("1. 종목 검색")
    search_query = st.sidebar.text_input(
        "종목명 또는 티커 검색",
        placeholder="(예: 삼성전자, Apple, Nvidia, BTC)",
        help="종목명이나 티커를 입력하여 검색하세요.",
        value="AAPL",
    )

    selected_ticker = search_query.upper()
    # 검색어가 있을 경우 검색 로직 수행
    if search_query:
        # 통합 검색 실행
        candidates = search_assets(search_query)

        if candidates:
            # 사용자에게 보여줄 옵션 구성 (포맷: 심볼 - 이름 [거래소])
            # 딕셔너리를 사용하여 선택된 라벨(Key)로 실제 티커(Value)를 찾습니다.
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
        # 검색어가 없을 때 기본 입력창 (기존 로직 유지 또는 안내)
        st.sidebar.caption("위 검색창에 종목명을 입력하세요. (기본값: AAPL)")
        selected_ticker = "AAPL"

    st.sidebar.info(f"선택된 티커: **{selected_ticker}**")

    st.sidebar.markdown("---")

    # =========================================================
    # 관심 종목 관리 섹션
    # =========================================================
    st.sidebar.subheader("📌 관심 종목 목록")

    user = st.session_state.get(SK_USER_INFO)
    user_id = user.get("id")  # 네이버면 id, 구글이면 sub 등으로 맞춰줘

    # 초기화 및 파일 로딩 (세션에 없을 때만 실행)
    if "watchlist" not in st.session_state:
        st.session_state[SK_WATCHLIST] = load_watchlist(user_id)

    # 텍스트 입력 창에 현재 검색된 티커를 기본값으로 제공
    # 'new_ticker_input'이라는 키로 텍스트 입력창이 관리됩니다.
    # 검색 결과(selected_ticker)를 이 키의 값으로 직접 넣어주면
    # 화면상의 입력창 값이 검색된 종목으로 자동 변경됩니다.

    # 선택된 티커가 바뀌었을 때만 입력창을 자동 업데이트
    if st.session_state.get(SK_LAST_SELECTED_TICKER) != selected_ticker.upper():
        st.session_state[SK_NEW_TICKER_INPUT] = selected_ticker.upper()
        st.session_state[SK_LAST_SELECTED_TICKER] = selected_ticker.upper()

    new_ticker = st.sidebar.text_input("목록에 추가할 종목", key=SK_NEW_TICKER_INPUT)

    # [추가] 버튼 로직
    if st.sidebar.button("➕ 관심 종목 등록"):
        if new_ticker:
            ticker_to_add = new_ticker.upper()
            if ticker_to_add not in st.session_state[SK_WATCHLIST]:
                # 종목 정보 가져오기
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
        # 리스트가 길어지면 스크롤이 생기도록 container 사용 가능 (선택사항)
        for item in st.session_state[SK_WATCHLIST]:
            ticker = item["ticker"]
            name = item["name"]
            cols = st.sidebar.columns([3, 1])
            cols[0].write(f"- {ticker} ({name})")

            # 제거 버튼 로직
            if cols[1].button("❌", key=f"remove_{ticker}"):
                remove_watchlist(user_id, ticker)
                st.session_state[SK_WATCHLIST] = load_watchlist(user_id)
                st.rerun()

    st.sidebar.markdown("---")

    # 차트 기간 설정
    period = st.sidebar.selectbox(
        "데이터 기간", ["1d", "5d", "1mo", "3mo", "6mo", "1y", "ytd", "max"], index=2
    )

    st.sidebar.markdown("---")

    # 자동 매매 조건 (목업)
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

    # 실행 버튼
    run_btn = st.sidebar.button("데이터 조회 및 적용", type="primary")

    return {
        "ticker": selected_ticker.upper(),
        "period": period,
        "run_btn": run_btn,
        "is_auto": is_auto_trading,
        "target_buy": target_buy_price,  # 추가됨
        "target_sell": target_sell_price,  # 추가됨
        "watchlist": st.session_state[SK_WATCHLIST],
    }
