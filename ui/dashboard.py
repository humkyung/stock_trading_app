# ui/dashboard.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

from modules.dart import ticker_to_corp_code, search_disclosures


def render_dashboard(df, basic_info, news_list, ticker=None):
    """
    수집된 데이터를 기반으로 메인 대시보드를 그립니다.
    """
    
    # 1. 상단 정보 요약 (KPI Metrics)
    if not df.empty and basic_info:
        current_price = df['Close'].iloc[-1]
        
        # 전일 대비 변동폭 계산 (데이터가 2개 이상일 때)
        if len(df) >= 2:
            prev_price = df['Close'].iloc[-2]
            delta_val = current_price - prev_price
            delta_pct = (delta_val / prev_price) * 100
        else:
            delta_val = 0
            delta_pct = 0

        # 3단 컬럼 레이아웃
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label=f"{basic_info['name']} ({basic_info['currency']})",
                value=f"{current_price:,.2f}",
                delta=f"{delta_val:,.2f} ({delta_pct:.2f}%)"
            )
        with col2:
            st.metric(label="시가총액", value=f"{basic_info['market_cap']:,}")
        with col3:
            st.metric(label="PER / EPS", value=f"{basic_info['per']} / {basic_info['eps']}")
            
        st.markdown("---")

    # 2. 메인 차트 (Plotly Candlestick)
    st.subheader("📊 시세 차트")
    if not df.empty:
        fig = go.Figure(data=[go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close']
        )])
        
        fig.update_layout(
            height=500,
            xaxis_rangeslider_visible=False, # 하단 슬라이더 제거 (깔끔하게)
            template="plotly_dark",  # 다크 모드 테마 적용
            title=f"{basic_info.get('name', 'Stock')} Price Movement"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("차트 데이터를 불러올 수 없습니다.")

    # 3. 하단 탭 (뉴스, 상세정보, 공시, 거래로그)
    tab1, tab2, tab3, tab4 = st.tabs(["📰 최신 뉴스", "ℹ️ 기업 개요", "📋 공시", "📝 매매 로그"])
    
    with tab1:
        if news_list:
            for news in news_list:
                with st.container():
                    st.markdown(f"#### [{news['title']}]({news['link']})")
                    col_news_1, col_news_2 = st.columns([1, 4])
                    with col_news_1:
                        # 썸네일 이미지가 있다면 표시 (없으면 생략)
                        if 'thumbnail' in news and news['thumbnail']:
                             # 썸네일 해상도 문제는 있을 수 있음
                            try:
                                st.image(news['thumbnail']['resolutions'][0]['url']) 
                            except Exception:
                                st.write("No Image")
                    with col_news_2:
                        raw_date = news.get('published')
                        date_str = "날짜 정보 없음"

                        if raw_date:
                            if isinstance(raw_date, (int, float)):  # 타임스탬프인 경우
                                date_str = datetime.fromtimestamp(raw_date).strftime('%Y-%m-%d %H:%M')
                            elif isinstance(raw_date, str):  # 문자열인 경우
                                try:
                                    date_obj = datetime.fromisoformat(raw_date)
                                    date_str = date_obj.strftime('%Y-%m-%d %H:%M')
                                except Exception:
                                    date_str = raw_date  # 포맷 변환 실패 시 원본 사용
                        st.caption(f"출처: {news['publisher']} | {date_str}")
                    st.divider()
        else:
            st.info("관련 뉴스가 없습니다.")

    with tab2:
        st.write(basic_info.get('summary', '기업 개요 정보가 없습니다.'))
        
    with tab3:
        _render_disclosure_tab(ticker)

    with tab4:
        st.write("자동 매매 기록이 이곳에 표시됩니다. (기능 구현 예정)")
        # 예시 데이터프레임
        dummy_log = pd.DataFrame({
            "시간": ["2023-10-25 10:00", "2023-10-25 14:30"],
            "주문": ["매수", "매도"],
            "가격": [150.00, 155.00],
            "수량": [10, 10]
        })
        st.dataframe(dummy_log, use_container_width=True)


def _render_disclosure_tab(ticker):
    """OpenDART 공시 검색 탭을 렌더링합니다."""
    if not ticker:
        st.info("종목을 선택하면 공시 정보를 조회할 수 있습니다.")
        return

    corp_code, corp_name = ticker_to_corp_code(ticker)
    if not corp_code:
        st.info("한국 상장 종목만 공시 검색이 가능합니다.")
        return

    st.caption(f"DART 기업코드: {corp_code} ({corp_name})")

    # 날짜 범위 선택
    col1, col2 = st.columns(2)
    with col1:
        bgn_date = st.date_input(
            "시작일",
            value=datetime.now() - timedelta(days=90),
            key="dart_bgn_date",
        )
    with col2:
        end_date = st.date_input(
            "종료일",
            value=datetime.now(),
            key="dart_end_date",
        )

    bgn_de = bgn_date.strftime("%Y%m%d")
    end_de = end_date.strftime("%Y%m%d")

    disclosures = search_disclosures(corp_code, bgn_de, end_de, page_count=50)

    if not disclosures:
        st.info("해당 기간에 공시 내역이 없습니다.")
        return

    st.caption(f"총 {len(disclosures)}건의 공시")

    for item in disclosures:
        rcept_no = item.get("rcept_no", "")
        report_nm = item.get("report_nm", "제목 없음")
        rcept_dt = item.get("rcept_dt", "")
        flr_nm = item.get("flr_nm", "")

        # 날짜 포맷팅
        if len(rcept_dt) == 8:
            date_display = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:]}"
        else:
            date_display = rcept_dt

        dart_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
        st.markdown(
            f"**[{report_nm}]({dart_url})**  \n"
            f"`{date_display}` · {flr_nm}"
        )
        st.divider()