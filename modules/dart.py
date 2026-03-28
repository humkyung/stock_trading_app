# modules/dart.py
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests
import streamlit as st

from modules.config import get_secret

DART_BASE_URL = "https://opendart.fss.or.kr/api"


def _get_api_key():
    return get_secret("OPEN_DART_API_KEY")


@st.cache_data(ttl=86400)  # 24시간 캐싱
def get_corp_code_map():
    """
    DART corpCode.xml을 다운로드하여 stock_code → corp_code 매핑을 반환합니다.
    Returns: dict[str, dict] - {"005930": {"corp_code": "00126380", "corp_name": "삼성전자"}, ...}
    """
    api_key = _get_api_key()
    if not api_key:
        return {}

    url = f"{DART_BASE_URL}/corpCode.xml"
    try:
        res = requests.get(url, params={"crtfc_key": api_key}, timeout=30)
        if res.status_code != 200:
            return {}

        # ZIP 파일 → XML 파싱
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            xml_name = zf.namelist()[0]
            with zf.open(xml_name) as f:
                tree = ET.parse(f)

        root = tree.getroot()
        mapping = {}
        for corp in root.iter("list"):
            stock_code = (corp.findtext("stock_code") or "").strip()
            corp_code = (corp.findtext("corp_code") or "").strip()
            corp_name = (corp.findtext("corp_name") or "").strip()

            if stock_code:  # 상장사만 (stock_code가 있는 기업)
                mapping[stock_code] = {
                    "corp_code": corp_code,
                    "corp_name": corp_name,
                }
        return mapping
    except Exception as e:
        print(f"DART corpCode 다운로드 실패: {e}")
        return {}


def ticker_to_corp_code(ticker: str):
    """
    yfinance 티커("005930.KS") → DART corp_code 변환.
    Returns: (corp_code, corp_name) 또는 (None, None)
    """
    # ".KS", ".KQ" 접미사 제거하여 6자리 종목코드 추출
    stock_code = ticker.split(".")[0]

    mapping = get_corp_code_map()
    if not mapping:
        return None, None

    info = mapping.get(stock_code)
    if info:
        return info["corp_code"], info["corp_name"]
    return None, None


@st.cache_data(ttl=300)  # 5분 캐싱
def search_disclosures(corp_code: str, bgn_de: str = None, end_de: str = None, page_count: int = 20):
    """
    DART 공시 검색 API 호출.
    Args:
        corp_code: 8자리 DART 기업 고유코드
        bgn_de: 검색 시작일 (YYYYMMDD)
        end_de: 검색 종료일 (YYYYMMDD)
        page_count: 결과 수 (최대 100)
    Returns: list[dict] - 공시 목록
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    if not bgn_de:
        bgn_de = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
    if not end_de:
        end_de = datetime.now().strftime("%Y%m%d")

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": page_count,
        "sort": "date",
        "sort_mth": "desc",
    }

    try:
        res = requests.get(f"{DART_BASE_URL}/list.json", params=params, timeout=10)
        data = res.json()

        if data.get("status") != "000":
            return []

        return data.get("list", [])
    except Exception as e:
        print(f"DART 공시 검색 실패: {e}")
        return []


def get_financial_statement(corp_code: str, bsns_year: str, reprt_code: str, fs_div: str = "CFS"):
    """
    DART 재무제표 API 호출.
    Args:
        corp_code: 8자리 DART 기업 고유코드
        bsns_year: 사업연도 (YYYY)
        reprt_code: 11013(1Q), 11012(반기), 11014(3Q), 11011(사업보고서)
        fs_div: CFS(연결) / OFS(개별)
    Returns: list[dict] - 재무제표 항목 리스트
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": fs_div,
    }

    try:
        res = requests.get(
            f"{DART_BASE_URL}/fnlttSinglAcntAll.json",
            params=params,
            timeout=10,
        )
        data = res.json()
        if data.get("status") != "000":
            return []
        return data.get("list", [])
    except Exception as e:
        print(f"DART 재무제표 조회 실패: {e}")
        return []
