# modules/portfolio.py
import pandas as pd


class PortfolioManager:
    """
    계좌 잔고 데이터를 가공하고 분석하는 클래스
    """

    def __init__(self, trader):
        self.trader = trader

    def get_portfolio_status(self):
        """
        현재 계좌 상태를 조회하여 보기 좋은 포맷으로 반환합니다.
        """
        holdings, summary = self.trader.get_balance()

        # 1. 계좌 요약 정보 처리
        if not summary:
            account_info = {
                "total_asset": 0,
                "total_profit": 0,
                "profit_rate": 0.0,
                "deposit": 0,
            }
        else:
            try:
                s_data = summary[0]
                account_info = {
                    "total_asset": int(s_data.get("tot_evlu_amt", 0)),
                    "total_profit": int(s_data.get("evlu_pfls_smtl_amt", 0)),
                    "profit_rate": float(s_data.get("evlu_pfls_rt", 0.0)),
                    "deposit": int(s_data.get("dnca_tot_amt", 0)),
                }
            except (IndexError, KeyError, TypeError, ValueError):
                account_info = {
                    "total_asset": 0,
                    "total_profit": 0,
                    "profit_rate": 0.0,
                    "deposit": 0,
                }

        # 2. 보유 종목 리스트 처리
        if not holdings:
            df = pd.DataFrame()
        else:
            try:
                df = pd.DataFrame(holdings)
                df = df[
                    [
                        "prdt_name",
                        "hldg_qty",
                        "pchs_avg_pric",
                        "prpr",
                        "evlu_pfls_amt",
                        "evlu_pfls_rt",
                    ]
                ]
                df.columns = [
                    "종목명",
                    "보유수량",
                    "매입가",
                    "현재가",
                    "평가손익",
                    "수익률(%)",
                ]
                df["보유수량"] = df["보유수량"].astype(int)
                df["매입가"] = df["매입가"].astype(float)
                df["현재가"] = df["현재가"].astype(float)
                df["평가손익"] = df["평가손익"].astype(int)
                df["수익률(%)"] = df["수익률(%)"].astype(float)
            except (KeyError, ValueError, TypeError) as e:
                print(f"보유 종목 데이터 처리 오류: {e}")
                df = pd.DataFrame()

        return account_info, df
