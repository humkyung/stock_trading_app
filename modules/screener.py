# modules/screener.py
import time
from datetime import datetime, timedelta

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from modules.dart import (
    get_corp_code_map,
    get_financial_statement,
    search_disclosures,
)
from modules.db import add_watchlist, load_watchlist
from ui.stock_search import get_krx_list

# 실적 관련 공시 키워드
DISCLOSURE_KEYWORDS = ["실적", "흑자전환", "매출증가", "영업이익", "잠정실적", "실적개선"]

# 분기 보고서 코드 (최신 → 과거 순)
REPRT_CODES = [
    ("11014", "3Q"),
    ("11012", "반기"),
    ("11013", "1Q"),
    ("11011", "사업보고서"),
]


def get_all_krx_tickers():
    """코스피/코스닥 전종목 리스트를 반환합니다."""
    df = get_krx_list()
    if df.empty:
        return []

    # KONEX 제외
    df = df[df["Market"].isin(["KOSPI", "KOSDAQ"])]

    tickers = []
    for _, row in df.iterrows():
        suffix = ".KS" if row["Market"] == "KOSPI" else ".KQ"
        tickers.append({
            "code": row["Code"],
            "name": row["Name"],
            "market": row["Market"],
            "ticker": f"{row['Code']}{suffix}",
        })
    return tickers


def check_dart_disclosures(corp_code, days=30):
    """최근 N일간 실적 관련 공시를 필터링합니다."""
    bgn_de = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    disclosures = search_disclosures(corp_code, bgn_de=bgn_de, page_count=50)

    relevant = []
    for d in disclosures:
        report_nm = d.get("report_nm", "")
        if any(kw in report_nm for kw in DISCLOSURE_KEYWORDS):
            relevant.append(d)
    return relevant


def _parse_amount(value):
    """재무제표 금액 문자열을 숫자로 변환합니다."""
    if not value:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def get_financial_turnaround(corp_code, year=None):
    """
    DART 재무제표에서 턴어라운드 여부를 판단합니다.
    Returns: dict | None
    """
    if not year:
        year = str(datetime.now().year)

    # 최신 분기부터 시도
    for reprt_code, _ in REPRT_CODES:
        # 연결재무제표 우선
        items = get_financial_statement(corp_code, year, reprt_code, "CFS")
        if not items:
            items = get_financial_statement(corp_code, year, reprt_code, "OFS")
        if not items:
            # 전년도 사업보고서도 시도
            if reprt_code == "11011":
                items = get_financial_statement(corp_code, str(int(year) - 1), reprt_code, "CFS")
                if not items:
                    items = get_financial_statement(corp_code, str(int(year) - 1), reprt_code, "OFS")
        if items:
            break

    if not items:
        return None

    revenue_cur = None
    revenue_prev = None
    op_profit_cur = None
    op_profit_prev = None

    for item in items:
        acct = item.get("account_nm", "")
        if acct in ["매출액", "영업수익", "수익(매출액)"]:
            revenue_cur = _parse_amount(item.get("thstrm_amount"))
            revenue_prev = _parse_amount(item.get("frmtrm_amount"))
        elif acct in ["영업이익", "영업이익(손실)"]:
            op_profit_cur = _parse_amount(item.get("thstrm_amount"))
            op_profit_prev = _parse_amount(item.get("frmtrm_amount"))

    if revenue_cur is None or op_profit_cur is None:
        return None

    # 성장률 계산
    revenue_growth = None
    if revenue_prev and revenue_prev != 0:
        revenue_growth = (revenue_cur - revenue_prev) / abs(revenue_prev) * 100

    op_growth = None
    if op_profit_prev and op_profit_prev != 0:
        op_growth = (op_profit_cur - op_profit_prev) / abs(op_profit_prev) * 100

    # 턴어라운드 조건
    is_turnaround = False
    # 1) 영업이익 적자 → 흑자 전환
    if op_profit_prev is not None and op_profit_prev < 0 and op_profit_cur > 0:
        is_turnaround = True
    # 2) 매출 20%+ 증가 & 영업이익 50%+ 증가
    elif (
        revenue_growth is not None
        and op_growth is not None
        and revenue_growth >= 20
        and op_growth >= 50
    ):
        is_turnaround = True

    return {
        "revenue": revenue_cur,
        "op_profit": op_profit_cur,
        "revenue_growth": revenue_growth,
        "op_growth": op_growth,
        "is_turnaround": is_turnaround,
    }


def calculate_indicators(df):
    """기술적 지표를 계산합니다. (pandas_ta 사용)"""
    close = df["Close"]

    df["MA20"] = ta.sma(close, length=20)
    df["MA60"] = ta.sma(close, length=60)
    df["RSI"] = ta.rsi(close, length=14)

    macd = ta.macd(close)
    if macd is not None:
        df["MACD"] = macd.iloc[:, 0]
        df["MACD_signal"] = macd.iloc[:, 1]

    bb = ta.bbands(close, length=20)
    if bb is not None:
        df["BB_upper"] = bb.iloc[:, 2]  # BBU
        df["BB_lower"] = bb.iloc[:, 0]  # BBL

    return df.dropna()


def score_stock(indicators_df, financials, disclosures):
    """
    종목 점수를 계산합니다 (0~12점).
    5점 이상이면 관심 종목 후보.
    """
    score = 0

    if indicators_df.empty:
        return score

    latest = indicators_df.iloc[-1]
    price = latest["Close"]

    # 기술적 지표 점수
    # RSI 30~50 (과매도 회복) → +2점
    rsi = latest.get("RSI")
    if rsi is not None and 30 <= rsi <= 50:
        score += 2

    # MACD > MACD_signal (골든크로스) → +2점
    macd = latest.get("MACD")
    macd_signal = latest.get("MACD_signal")
    if macd is not None and macd_signal is not None and macd > macd_signal:
        score += 2

    # 가격 > MA20 > MA60 (정배열) → +2점
    ma20 = latest.get("MA20")
    ma60 = latest.get("MA60")
    if ma20 is not None and ma60 is not None and price > ma20 > ma60:
        score += 2

    # BB_lower 근처 (하단 바운스) → +1점
    bb_lower = latest.get("BB_lower")
    bb_upper = latest.get("BB_upper")
    if bb_lower is not None and bb_upper is not None:
        bb_range = bb_upper - bb_lower
        if bb_range > 0 and (price - bb_lower) / bb_range < 0.3:
            score += 1

    # 재무 점수
    if financials:
        if financials.get("is_turnaround"):
            score += 3
        elif financials.get("revenue_growth") and financials["revenue_growth"] > 0:
            score += 1

    # 공시 점수
    if disclosures:
        score += 1

    return score


def run_screening(progress_callback=None):
    """
    전종목 스크리닝을 실행합니다.
    Args:
        progress_callback: 진행률 콜백 (current, total, stock_name)
    Returns: list[dict] - 점수 5점 이상 종목 리스트
    """
    all_tickers = get_all_krx_tickers()
    corp_map = get_corp_code_map()
    total = len(all_tickers)
    results = []

    for i, stock in enumerate(all_tickers):
        if progress_callback:
            progress_callback(i, total, stock["name"])

        code = stock["code"]
        ticker = stock["ticker"]

        # corp_code 매핑
        corp_info = corp_map.get(code)
        if not corp_info:
            continue
        corp_code = corp_info["corp_code"]

        try:
            # 1) 가격 데이터 (최근 100일)
            yf_ticker = yf.Ticker(ticker)
            df = yf_ticker.history(period="100d")
            if df.empty or len(df) < 60:
                continue

            # 2) 기술적 지표
            indicators_df = calculate_indicators(df)
            if indicators_df.empty:
                continue

            # 3) DART 공시 확인
            disclosures = check_dart_disclosures(corp_code, days=30)

            # 4) 재무 턴어라운드 확인
            financials = get_financial_turnaround(corp_code)

            # 5) 점수 계산
            score = score_stock(indicators_df, financials, disclosures)

            if score >= 5:
                latest = indicators_df.iloc[-1]
                results.append({
                    "ticker": ticker,
                    "name": stock["name"],
                    "market": stock["market"],
                    "score": score,
                    "price": latest["Close"],
                    "rsi": round(latest.get("RSI", 0), 1),
                    "revenue_growth": round(financials["revenue_growth"], 1) if financials and financials.get("revenue_growth") else None,
                    "op_growth": round(financials["op_growth"], 1) if financials and financials.get("op_growth") else None,
                    "is_turnaround": financials.get("is_turnaround", False) if financials else False,
                    "disclosures": len(disclosures),
                })

        except Exception as e:
            print(f"{ticker} 스크리닝 오류: {e}")
            continue

        # API rate limit 대응
        time.sleep(0.5)

    # 점수 내림차순 정렬
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def register_screened_stocks(user_id, stocks):
    """스크리닝 결과를 관심 종목 DB에 등록합니다."""
    existing = load_watchlist(user_id)
    existing_tickers = {item["ticker"] for item in existing}

    registered = 0
    for stock in stocks:
        if stock["ticker"] not in existing_tickers:
            add_watchlist(user_id, stock["ticker"], stock["name"])
            registered += 1

    return registered
