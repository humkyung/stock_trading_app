# ui/portfolio_ui.py
import streamlit as st
import plotly.express as px


def render_portfolio_dashboard(account_info, df):
    """
    포트폴리오 현황을 시각화합니다.
    """
    st.header("💰 나의 자산 현황")

    # 1. 계좌 요약 (Metrics)
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("총 평가 자산", f"{account_info['total_asset']:,}원")
    col2.metric("예수금 (주문가능)", f"{account_info['deposit']:,}원")

    # 수익이면 빨강(한국 기준), 손실이면 파랑
    profit_color = "normal"
    if account_info["total_profit"] > 0:
        profit_color = "off"  # Streamlit delta logic

    col3.metric(
        "총 평가 손익",
        f"{account_info['total_profit']:,}원",
        delta=f"{account_info['profit_rate']}%",
    )

    st.markdown("---")

    # 2. 보유 종목 분석
    if not df.empty:
        col_chart, col_table = st.columns([1, 2])

        with col_chart:
            st.subheader("📊 자산 비중")
            # 평가금액 기준 파이 차트
            df["평가금액"] = df["현재가"] * df["보유수량"]
            fig = px.pie(df, values="평가금액", names="종목명", hole=0.4)
            fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)

        with col_table:
            st.subheader("📝 보유 종목 상세")
            # 스타일링: 수익률에 따라 색상 표시
            st.dataframe(
                df.style.format(
                    {
                        "매입가": "{:,.0f}",
                        "현재가": "{:,.0f}",
                        "평가손익": "{:,.0f}",
                        "수익률(%)": "{:.2f}%",
                    }
                ).background_gradient(
                    subset=["수익률(%)"], cmap="RdYlGn", vmin=-10, vmax=10
                ),
                use_container_width=True,
                height=300,
            )
    else:
        st.info("현재 보유 중인 주식이 없습니다.")
