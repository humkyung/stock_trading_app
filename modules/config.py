# modules/config.py
import os

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

load_dotenv()


def get_secret(key: str, default=None):
    """Streamlit secrets를 우선 확인하고, 없으면 os.getenv로 폴백."""
    try:
        if key in st.secrets:
            return st.secrets.get(key, default)
    except StreamlitSecretNotFoundError:
        pass
    return os.getenv(key, default)
