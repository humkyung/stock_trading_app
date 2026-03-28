# ui/stock_search.py
import re

import FinanceDataReader as fdr
import pandas as pd
import requests
import streamlit as st


@st.cache_data
def get_krx_list():
    """
    한국거래소(KRX) 상장 종목 전체 리스트를 가져와 캐싱합니다.
    """
    try:
        df = fdr.StockListing("KRX")
        return df[["Code", "Name", "Market"]]
    except Exception as e:
        st.warning(f"KRX Listing(FDR) 실패 → CSV 백업으로 폴백: {repr(e)}")

        backup_url = "https://raw.githubusercontent.com/corazzon/finance-data-analysis/main/krx.csv"
        try:
            df = pd.read_csv(backup_url)
            if "Symbol" in df.columns and "Code" not in df.columns:
                df = df.rename(columns={"Symbol": "Code"})
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
    """캐시된 KRX 리스트에서 종목명 또는 코드로 검색합니다."""
    df = get_krx_list()
    if df.empty:
        return []

    mask = df["Name"].str.contains(query, case=False) | df["Code"].str.contains(query)
    results_df = df[mask]

    search_results = []
    for _, row in results_df.head(10).iterrows():
        market_suffix = ""
        if row["Market"] in ["KOSPI"]:
            market_suffix = ".KS"
        elif row["Market"] in ["KOSDAQ", "KONEX"]:
            market_suffix = ".KQ"

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


def search_yahoo_market(query):
    """Yahoo Finance API를 이용해 미국 주식, ETF, 코인을 검색합니다."""
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        params = {"q": query, "quotesCount": 10, "newsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers, params=params, timeout=3)
        data = response.json()

        results = []
        if "quotes" in data:
            for item in data["quotes"]:
                if "symbol" in item:
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
    return bool(re.compile("[가-힣]").search(text))


def search_assets(query):
    """입력 언어에 따라 검색 엔진을 분기합니다."""
    if not query:
        return []
    if contains_korean(query):
        return search_krx_market(query)
    if query.isdigit() and len(query) == 6:
        return search_krx_market(query)
    return search_yahoo_market(query)
