#modules/auth_manager.py 
import os
import requests
import urllib.parse
import streamlit as st
from dotenv import load_dotenv
import secrets
from streamlit.errors import StreamlitSecretNotFoundError

class AuthManager:
    def __init__(self):
        # 로컬 .env 로딩 (Streamlit Cloud에서는 보통 영향 없음)
        load_dotenv()

        # Streamlit Cloud에서는 st.secrets가 정석
        def get_secret(key: str):
            # 1) Streamlit secrets가 존재하는 환경(Cloud 등)에서는 secrets 우선
            try:
                if hasattr(st, "secrets") and key in st.secrets:
                    return st.secrets[key]
            except StreamlitSecretNotFoundError:
                # secrets.toml 자체가 없는 로컬 환경이면 여기로 떨어짐
                pass
            return os.getenv(key)

        # Google 설정
        self.google_client_id = get_secret("GOOGLE_CLIENT_ID")
        self.google_client_secret = get_secret("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = get_secret("GOOGLE_REDIRECT_URI")
        
        # Naver 설정
        self.naver_client_id = get_secret("NAVER_CLIENT_ID")
        self.naver_client_secret = get_secret("NAVER_CLIENT_SECRET")
        self.naver_redirect_uri = get_secret("NAVER_REDIRECT_URI")

    def _require(self, **kwargs):
        missing = [k for k, v in kwargs.items() if not v]
        if missing:
            raise ValueError(f"필수 설정 누락: {', '.join(missing)}")

    def get_google_auth_url(self):
        """Google 로그인 URL 생성"""

        self._require(
            GOOGLE_CLIENT_ID=self.google_client_id,
            GOOGLE_REDIRECT_URI=self.google_redirect_uri,
        )
        params = {
            "client_id": self.google_client_id,
            "redirect_uri": self.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"


    def get_naver_auth_url(self):
        """Naver 로그인 URL 생성"""

        self._require(
            NAVER_CLIENT_ID=self.naver_client_id,
            NAVER_REDIRECT_URI=self.naver_redirect_uri,
        )

        # state를 랜덤 생성 + 세션에 저장(콜백에서 검증)
        state = secrets.token_urlsafe(16)
        st.session_state["naver_oauth_state"] = state

        params = {
            "client_id": self.naver_client_id,
            "redirect_uri": self.naver_redirect_uri,
            "response_type": "code",
            "state": state
        }
        return f"https://nid.naver.com/oauth2.0/authorize?{urllib.parse.urlencode(params)}"

    def authenticate_google(self, code):
        """Google 인증 코드로 사용자 정보 가져오기"""
        # 1. 토큰 교환
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": self.google_client_id,
            "client_secret": self.google_client_secret,
            "redirect_uri": self.google_redirect_uri,
            "grant_type": "authorization_code"
        }
        res = requests.post(token_url, data=data)
        if res.status_code != 200:
            return None
        
        token_info = res.json()
        access_token = token_info.get("access_token")

        # 2. 사용자 정보 조회
        user_info_url = "https://www.googleapis.com/oauth2/v1/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_res = requests.get(user_info_url, headers=headers)
        
        if user_res.status_code == 200:
            return user_res.json() # {id, email, name, picture...}
        return None

    def authenticate_naver(self, code, state):
        """Naver 인증 코드로 사용자 정보 가져오기"""
        # state 검증(권장)
        expected = st.session_state.get("naver_oauth_state")
        if expected and state != expected:
            return None

        self._require(
            NAVER_CLIENT_ID=self.naver_client_id,
            NAVER_CLIENT_SECRET=self.naver_client_secret,
        )

        # 1. 토큰 교환
        token_url = "https://nid.naver.com/oauth2.0/token"
        params = {
            "grant_type": "authorization_code",
            "client_id": self.naver_client_id,
            "client_secret": self.naver_client_secret,
            "code": code,
            "state": state
        }
        res = requests.get(token_url, params=params, timeout=10)
        if res.status_code != 200:
            return None
            
        token_info = res.json()
        access_token = token_info.get("access_token")
        if not access_token:
            return None

        # 2. 사용자 정보 조회
        user_info_url = "https://openapi.naver.com/v1/nid/me"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_res = requests.get(user_info_url, headers=headers, timeout=10)
        if user_res.status_code == 200:
            return user_res.json().get('response') # {id, email, name, profile_image...}
        return None