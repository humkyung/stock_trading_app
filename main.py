#main.py
import streamlit as st
import yfinance as yf

st.title("📈 자동 주식 매매 시스템") 
st.write("설정된 종목의 실시간 시세를 모니터링합니다.") 
ticker = st.text_input("종목 코드 입력 (예: AAPL, 005930.KS)", "AAPL") 

if st.button("조회"): 
    data = yf.Ticker(ticker).history(period="1d")
    st.dataframe(data)
    st.line_chart(data['Close'])

