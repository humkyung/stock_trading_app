# ui/login_page.py
import streamlit as st

def render_login_page(auth_manager):
    """
    로그인 버튼이 있는 화면을 렌더링합니다.
    """
    st.markdown(
        """
        <style>
        .login-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin-top: 100px;
            padding: 50px;
            border-radius: 10px;
            background-color: #f0f2f6;
        }
        .login-btn {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            text-decoration: none;
            color: white;
            text-align: center;
            font-weight: bold;
            display: block;
        }
        .google { background-color: #DB4437; }
        .naver { background-color: #03C75A; }
        h1 { text-align: center; }
        </style>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1>🔐 로그인</h1>", unsafe_allow_html=True)
        st.write("서비스를 이용하려면 로그인이 필요합니다.")
        
        # Google 로그인 버튼
        try:
            google_url = auth_manager.get_google_auth_url()
            st.markdown(f'<a href="{google_url}" class="login-btn google" target="_self">Google 계정으로 로그인</a>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Google 로그인 설정 오류: {e}")
        
        # Naver 로그인 버튼
        try:
            naver_url = auth_manager.get_naver_auth_url()
            st.markdown(f'<a href="{naver_url}" class="login-btn naver" target="_self">Naver 계정으로 로그인</a>', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"네이버 로그인 설정 오류: {e}")