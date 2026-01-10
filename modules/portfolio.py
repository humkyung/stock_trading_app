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
            # summary는 리스트 형태이며 첫 번째 요소에 데이터가 있음
            s_data = summary[0]
            account_info = {
                "total_asset": int(s_data.get("tot_evlu_amt", 0)),  # 총 평가 금액
                "total_profit": int(
                    s_data.get("evlu_pfls_smtl_amt", 0)
                ),  # 평가 손익 합계
                "profit_rate": float(s_data.get("evlu_pfls_rt", 0.0)),  # 수익률
                "deposit": int(s_data.get("dnca_tot_amt", 0)),  # 예수금
            }

        # 2. 보유 종목 리스트 처리
        if not holdings:
            df = pd.DataFrame()
        else:
            # 필요한 컬럼만 추출 및 이름 변경
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

            # 숫자형 변환 (API는 문자열로 줌)
            df["보유수량"] = df["보유수량"].astype(int)
            df["매입가"] = df["매입가"].astype(float)
            df["현재가"] = df["현재가"].astype(float)
            df["평가손익"] = df["평가손익"].astype(int)
            df["수익률(%)"] = df["수익률(%)"].astype(float)

        return account_info, df
