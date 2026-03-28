# modules/scraper.py
import yfinance as yf
import pandas as pd
import streamlit as st


class StockScraper:
    """
    Yahoo Finance API를 사용하여 주식 정보를 수집하는 클래스
    """

    def __init__(self, ticker):
        self.ticker_symbol = ticker
        self.stock = yf.Ticker(ticker)

    def get_current_price(self):
        """
        실시간(혹은 최근) 현재가를 반환합니다.
        """
        try:
            # fast_info가 응답 속도가 더 빠릅니다.
            return self.stock.fast_info["last_price"]
        except Exception:
            # fast_info 실패 시 일반 info에서 시도
            data = self.stock.history(period="1d")
            if not data.empty:
                return data["Close"].iloc[-1]
            return None

    def get_history(self, period="1mo", interval="1d"):
        """
        지정된 기간 동안의 주가 이력(OHLCV) 데이터를 DataFrame으로 반환합니다.

        Args:
            period (str): 데이터 기간 (예: '1d', '1mo', '1y', 'max')
            interval (str): 데이터 간격 (예: '1m', '1h', '1d', '1wk')
        """
        try:
            df = self.stock.history(period=period, interval=interval)

            # 데이터가 비어있는 경우 처리
            if df.empty:
                return pd.DataFrame()

            # 가독성을 위해 인덱스(날짜) 포맷 정리 (선택 사항)
            # df.index = df.index.strftime('%Y-%m-%d %H:%M')

            return df
        except Exception as e:
            st.error(f"데이터 수집 중 오류 발생: {e}")
            return pd.DataFrame()

    def get_basic_info(self):
        """
        종목의 기본 재무 정보 및 기업 개요를 반환합니다.
        """
        try:
            info = self.stock.info
            # 필요한 정보만 추출하여 딕셔너리로 반환
            essential_info = {
                "name": info.get("longName", "N/A"),
                "currency": info.get("currency", "USD"),
                "market_cap": info.get("marketCap", 0),
                "per": info.get("trailingPE", 0),
                "eps": info.get("trailingEps", 0),
                "sector": info.get("sector", "N/A"),
                "summary": info.get("longBusinessSummary", "정보 없음"),
            }
            return essential_info
        except Exception as e:
            return None

    def get_news(self, limit=5):
        """
        해당 종목과 관련된 최신 뉴스를 가져옵니다.
        """
        try:
            raw_news = self.stock.news
            clean_news_list = []

            for item in raw_news:
                # 데이터가 'content' 키 안에 래핑되어 있는 경우 처리
                content = item.get("content", item)  # content가 없으면 item 자체를 사용

                # 필요한 정보만 뽑아서 깔끔한 딕셔너리로 만듦
                news_data = {
                    "title": content.get("title", "제목 없음"),
                    "link": (content.get("clickThroughUrl") or {}).get("url", "#"),
                    "publisher": (content.get("provider") or {}).get(
                        "displayName", "Yahoo Finance"
                    ),
                    "thumbnail": None,
                    "published": content.get("pubDate")
                    or content.get("providerPublishTime"),
                }

                # 썸네일 처리 (있을 경우)
                if "thumbnail" in content and "resolutions" in content["thumbnail"]:
                    resolutions = content["thumbnail"]["resolutions"]
                    if resolutions:
                        news_data["thumbnail"] = resolutions[0]["url"]

                clean_news_list.append(news_data)

            # 최신순으로 limit 개수만큼만 반환
            return clean_news_list[:limit]
        except Exception as e:
            # 에러 발생 시 빈 리스트 반환하여 UI 깨짐 방지
            print(f"뉴스 수집 중 에러: {e}")
            return []


# Streamlit 캐싱을 위한 래퍼 함수 (main.py에서 호출 시 사용)
@st.cache_data(ttl=300)  # 300초(5분)마다 데이터 갱신
def fetch_stock_history(ticker, period="1mo"):
    scraper = StockScraper(ticker)
    return scraper.get_history(period=period)


@st.cache_data(ttl=3600)  # 기본 정보는 1시간 캐싱
def fetch_stock_info(ticker):
    scraper = StockScraper(ticker)
    return scraper.get_basic_info()


# 상수를 정의합니다. (이 값을 바꾸면 로직과 UI 텍스트가 동시에 바뀝니다)
WATCHLIST_UPDATE_SEC = 60


@st.cache_data(ttl=WATCHLIST_UPDATE_SEC)  # 60초(1분)마다 데이터 갱신
def fetch_watchlist_data(tickers):
    """
    관심 종목 리스트의 핵심 정보를 일괄적으로 가져옵니다.
    """
    if not tickers:
        return pd.DataFrame()

    try:
        # yfinance를 사용하여 여러 종목의 현재 데이터를 가져옵니다.
        # Ticker 객체의 info에서 last_price, marketCap, trailingPE 등을 추출할 수 있습니다.
        data_list = []
        for tickerInfo in tickers:
            ticker = tickerInfo["ticker"]
            stock_name = tickerInfo["name"]
            yfticker = yf.Ticker(ticker)
            info = yfticker.fast_info  # 빠른 정보 조회

            try:
                # fast_info는 딕셔너리가 아닌 객체이므로 .last_price 등으로 접근합니다.
                # 참고: fast_info에는 PER, 섹터 정보가 포함되지 않는 경우가 많습니다.
                last_price = info.last_price if hasattr(info, "last_price") else None
                market_cap = info.market_cap if hasattr(info, "market_cap") else None

                # 가격 정보가 있는 경우에만 리스트에 추가
                if last_price is not None:
                    data_list.append(
                        {
                            "종목코드": ticker,
                            "종목이름": stock_name,
                            "현재가": last_price,
                            "시가총액": market_cap if market_cap else "N/A",
                            # fast_info는 실시간 가격 중심이므로 PER/섹터 정보는 없을 수 있음 (N/A 처리)
                            "PER": "N/A",
                            "섹터": "N/A",
                        }
                    )
            except Exception as e:
                # 특정 종목 데이터 추출 실패 시 로그만 찍고 다음 종목으로 진행
                print(f"{ticker} 데이터 처리 중 오류: {e}")
                continue

        df = pd.DataFrame(data_list)
        # 필요한 경우 데이터 정제 및 포맷팅 (예: 시가총액 단위 조정)

        return df

    except Exception as e:
        st.error(f"관심 종목 데이터 수집 중 오류 발생: {e}")
        return pd.DataFrame()
