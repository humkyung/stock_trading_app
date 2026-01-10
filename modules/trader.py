# modules/trader.py
import os
import requests
import json
from datetime import datetime, timedelta
import streamlit as st
from dotenv import load_dotenv

TOKEN_FILE = "token.json"
TOKEN_SAFETY_MIN = 5  # 만료 5분 전이면 갱신
TOKEN_EXPIRE_HOURS = 23  # 24시간보다 조금 짧게

# .env 파일 로드
load_dotenv()


class KisTrader:
    """
    한국투자증권(KIS) REST API 연동 클래스
    """

    def __init__(self):
        self.mode = os.getenv("KIS_MODE", "VIRTUAL")
        self.app_key = os.getenv("KIS_APP_KEY")
        self.app_secret = os.getenv("KIS_APP_SECRET")
        self.account_no = os.getenv("KIS_ACCOUNT_NO")  # 계좌번호 앞 8자리
        self.account_code = os.getenv("KIS_ACCOUNT_CODE", "01")  # 계좌번호 뒤 2자리

        # 모의투자 vs 실전투자 URL 설정
        if self.mode == "PROD":
            self.base_url = "https://openapi.koreainvestment.com:9443"
        else:
            self.base_url = "https://openapivts.koreainvestment.com:29443"

        self.access_token = None
        self._auth()  # 초기화 시 바로 인증 토큰 발급 시도

    def _auth(self):
        """
        접근 토큰(Access Token) 발급 (1일 1회 갱신 필요)
        """
        # 1️⃣ 캐시된 토큰 먼저 확인

        cached_token, issued_at = self._load_cached_token()
        if cached_token:
            self.access_token = cached_token
            self.token_issued_at = issued_at  # issue 날짜 저장
            print("♻️ 캐시된 토큰 사용")
            return

        # 2️⃣ 없으면 새로 발급
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        try:
            res = requests.post(url, headers=headers, data=json.dumps(body))
            if res.status_code == 200:
                self.access_token = res.json()["access_token"]
                self.token_issued_at = datetime.now()
                self._save_token(self.access_token)  # 토큰 저장
                print("✅ 한국투자증권 토큰 발급 성공(새로 발급)")
            else:
                print(f"❌ 토큰 발급 실패: {res.text}")
                self.access_token = None
                self.token_issued_at = None
        except Exception as e:
            print(f"❌ 인증 중 오류 발생: {e}")
            self.access_token = None
            self.token_issued_at = None

    def _load_cached_token(self):
        if not os.path.exists(TOKEN_FILE):
            return None, None

        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            token = data.get("access_token")
            issued_at = datetime.fromisoformat(data["issued_at"])

            if not token or not issued_at:
                return None, None

            if datetime.now() - issued_at < timedelta(hours=TOKEN_EXPIRE_HOURS):
                return token, issued_at

        except Exception:
            return None, None

        return None, None

    def _save_token(self, token: str):
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "access_token": token,
                    "issued_at": datetime.now().isoformat(),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _ensure_token(self):
        if not self.access_token or not self.token_issued_at:
            self._auth()
            return

        # issued_at 기준 23시간 초과 시 재발급
        if datetime.now() - self.token_issued_at >= timedelta(hours=TOKEN_EXPIRE_HOURS):
            print("🔄 토큰 23시간 초과 → 재발급")
            self._auth()

    def _get_common_headers(self, tr_id):
        """
        API 호출에 필요한 공통 헤더 생성
        """
        self._ensure_token()
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

    def get_balance(self):
        """
        주식 잔고 조회 (TTTC8434R: 주식잔고조회_실전 / VTTC8434R: 주식잔고조회_모의)
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"

        # 모의투자와 실전투자 TR ID가 다름
        tr_id = "VTTC8434R" if self.mode == "VIRTUAL" else "TTTC8434R"

        headers = self._get_common_headers(tr_id)

        params = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
            if res.status_code == 200 and data["rt_cd"] == "0":
                # output1: 보유 종목 리스트, output2: 계좌 총 자산 현황
                return data["output1"], data["output2"]
            else:
                print(f"잔고 조회 실패: {data.get('msg1')}")
                return [], []
        except Exception as e:
            print(f"잔고 조회 에러: {e}")
            return [], []

    def send_order(self, ticker, quantity, price, order_type="buy"):
        """
        주문 실행 (지정가 기준)
        Args:
            ticker: 종목코드 (6자리)
            quantity: 수량
            price: 가격 (0이면 시장가)
            order_type: 'buy' (매수) or 'sell' (매도)
        """
        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"

        # TR ID 설정 (매수/매도 구분)
        if self.mode == "VIRTUAL":
            tr_id = "VTTC0802U" if order_type == "buy" else "VTTC0801U"
        else:
            tr_id = "TTTC0802U" if order_type == "buy" else "TTTC0801U"

        headers = self._get_common_headers(tr_id)

        data = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_code,
            "PDNO": ticker,
            "ORD_DVSN": "01",  # 00:지정가, 01:시장가
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if price > 0 else "0",
        }

        # 지정가일 경우 '00'으로 변경
        if price > 0:
            data["ORD_DVSN"] = "00"

        try:
            res = requests.post(url, headers=headers, data=json.dumps(data))
            result = res.json()
            if result["rt_cd"] == "0":
                print(f"✅ {order_type} 주문 성공: {result['msg1']}")
                return True
            else:
                print(f"❌ 주문 실패: {result['msg1']}")
                return False
        except Exception as e:
            print(f"❌ 주문 중 에러: {e}")
            return False
