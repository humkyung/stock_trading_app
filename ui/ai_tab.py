# ui/ai_tab.py
"""
AI 투자 비서 탭 렌더링
각 섹션을 독립 함수로 분리해 가독성과 유지보수성을 높였습니다.

섹션 구성:
  _render_css()            - 탭 전용 스타일 주입
  _render_header()         - 포트폴리오 요약 메트릭
  _render_analyze_button() - 전체/개별 분석 버튼 + 진행 바
  _render_stock_cards()    - 종목 카드 그리드
  _render_detail_tabs()    - 종목별 상세 분석 탭
  _render_alerts()         - 관리 필요 종목 경보
  _render_cash_strategy()  - 예수금 활용 전략
  render_ai_tab()          - 진입점 (main.py에서 호출)
"""

import time
import streamlit as st
from modules.ai_analyst import analyze_stock, score_color, ACTION_COLOR

# ── 포트폴리오 데이터 ─────────────────────────────────────────────────────────
# TODO: 추후 data/portfolio.py 로 분리 예정
PORTFOLIO = [
    {
        "name": "삼성전자",
        "ticker": "KRX:005930",
        "code": "005930",
        "currency": "KRW",
        "amount": 20_538_200,
        "bookPrice": 199_400,
        "shares": 103,
    },
    {
        "name": "알파벳 A",
        "ticker": "NASDAQ:GOOGL",
        "code": "GOOGL",
        "currency": "USD",
        "amount": 11_488_121,
        "bookPrice": None,
        "shares": None,
    },
    {
        "name": "엔비디아",
        "ticker": "NASDAQ:NVDA",
        "code": "NVDA",
        "currency": "USD",
        "amount": 7_132_207,
        "bookPrice": None,
        "shares": None,
    },
    {
        "name": "에코프로비엠",
        "ticker": "KOSDAQ:247540",
        "code": "247540",
        "currency": "KRW",
        "amount": 6_716_500,
        "bookPrice": 191_900,
        "shares": 35,
    },
    {
        "name": "현대차",
        "ticker": "KRX:005380",
        "code": "005380",
        "currency": "KRW",
        "amount": 5_742_000,
        "bookPrice": 517_000,
        "shares": 11,
    },
    {
        "name": "SK하이닉스",
        "ticker": "KRX:000660",
        "code": "000660",
        "currency": "KRW",
        "amount": 5_030_000,
        "bookPrice": 1_007_000,
        "shares": 5,
    },
    {
        "name": "삼성전기",
        "ticker": "KRX:009150",
        "code": "009150",
        "currency": "KRW",
        "amount": 3_716_000,
        "bookPrice": 464_500,
        "shares": 8,
    },
    {
        "name": "디아이씨",
        "ticker": "KRX:092200",
        "code": "092200",
        "currency": "KRW",
        "amount": 2_292_500,
        "bookPrice": 9_170,
        "shares": 250,
    },
    {
        "name": "비자",
        "ticker": "NYSE:V",
        "code": "V",
        "currency": "USD",
        "amount": 2_278_824,
        "bookPrice": None,
        "shares": None,
    },
]
CASH = 858_503
ETF = 1_600_000
TOTAL = sum(s["amount"] for s in PORTFOLIO) + ETF + CASH

# 관리 필요 종목 판단 기준
_ALERT_ACTIONS = {"즉시 비중 축소", "전량 매도 검토", "추가 매수 보류"}
_GOLDEN_ACTIONS = {"비중 확대", "핵심 유지", "눌림목 추가"}


# ── 섹션 1: CSS ───────────────────────────────────────────────────────────────
def _render_css() -> None:
    st.markdown(
        """
        <style>
        .ai-card {
            background:#0d1120; border:1px solid #1a2540;
            border-radius:14px; padding:18px 20px; margin-bottom:10px;
            position:relative; overflow:hidden;
        }
        .ai-section {
            background:#080d1a; border:1px solid #1a2540;
            border-radius:12px; padding:16px 18px; margin-bottom:12px;
        }
        .ai-badge {
            display:inline-block; font-size:11px; font-weight:600;
            padding:3px 10px; border-radius:20px; margin-right:6px;
        }
        .ai-news-item {
            font-size:11px; color:#7eb8ff; padding:5px 8px;
            background:#0a1525; border-radius:6px; margin-bottom:4px;
            border-left:2px solid #1e4a8a;
        }
        .ai-alert {
            border-radius:12px; padding:16px 18px; margin-bottom:8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── 섹션 2: 헤더 ─────────────────────────────────────────────────────────────
def _render_header(avg_score: float | None) -> None:
    h1, h2, h3, h4 = st.columns([3, 1.5, 1.5, 1.5])
    with h1:
        st.markdown("### 📊 AI 투자 비서")
        st.caption("웹 검색 기반 실시간 종목 분석")
    with h2:
        st.metric("포트폴리오 총액", f"₩{TOTAL:,}")
    with h3:
        st.metric("예수금", f"₩{CASH:,}")
    with h4:
        if avg_score is not None:
            st.metric("종합 매력도", f"{avg_score:.1f}/10")


# ── 섹션 3: 전체 분석 버튼 ───────────────────────────────────────────────────
def _store_and_show_error(name: str, code: str, error: Exception) -> None:
    """분석 오류를 세션에 저장하고 경고 메시지를 표시합니다."""
    st.session_state["ai_analyses"][code] = {"error": str(error)}
    st.warning(f"{name} 분석 실패: {error}")


def _render_analyze_button(api_key: str, analyses: dict) -> None:
    completed = len(analyses)
    btn_label = "🚀 전체 분석 시작" if completed == 0 else "🔄 전체 재분석"

    if not st.button(btn_label, key="ai_analyze_all"):
        return

    st.session_state["ai_analyses"] = {}
    progress_bar = st.progress(0, text="분석 준비 중...")

    for i, stock in enumerate(PORTFOLIO):
        progress_bar.progress(
            i / len(PORTFOLIO),
            text=f"🔍 {stock['name']} 분석 중... ({i + 1}/{len(PORTFOLIO)}) — 다음 종목까지 약 15초 대기 중",
        )
        try:
            st.session_state["ai_analyses"][stock["code"]] = analyze_stock(
                stock, api_key
            )
        except Exception as e:
            _store_and_show_error(stock["name"], stock["code"], e)
        time.sleep(15)  # Rate limit 대응: 분당 30,000 토큰 제한 → 종목당 15초 간격

    progress_bar.progress(1.0, text="✅ 분석 완료!")
    time.sleep(0.6)
    st.rerun()


# ── 섹션 4: 종목 카드 그리드 ─────────────────────────────────────────────────
def _render_stock_cards(api_key: str, analyses: dict) -> None:
    st.markdown("#### 보유 종목 현황")
    cols = st.columns(3)

    for idx, stock in enumerate(PORTFOLIO):
        code = stock["code"]
        a = analyses.get(code)
        weight = stock["amount"] / TOTAL * 100

        with cols[idx % 3]:
            _render_single_card(stock, a, weight)

            # 개별 분석 버튼 (미분석 종목에만 표시)
            if not a:
                if st.button("🔍 개별 분석", key=f"ai_btn_{code}"):
                    with st.spinner(f"{stock['name']} 분석 중..."):
                        try:
                            st.session_state["ai_analyses"][code] = analyze_stock(
                                stock, api_key
                            )
                        except Exception as e:
                            st.session_state["ai_analyses"][code] = {"error": str(e)}
                    st.rerun()


def _render_single_card(stock: dict, a: dict | None, weight: float) -> None:
    """종목 카드 1개 HTML 생성 및 렌더링"""
    sc = a.get("score") if a and not a.get("error") else None
    bar_c = score_color(sc)
    bar_pct = f"{(sc or 0) * 10}%"

    # 장부가 표시
    book_html = ""
    if stock["bookPrice"]:
        sym = "₩" if stock["currency"] == "KRW" else "$"
        book_html = f"<div style='font-size:11px;color:#5a7099;margin-top:4px'>장부가 {sym}{stock['bookPrice']:,}</div>"

    # 분석 결과 표시
    price_html = badges_html = summary_html = ""
    if a and not a.get("error"):
        act = a.get("action", "")
        ac = ACTION_COLOR.get(act, "#aaa")
        ud_c = "#00e5a0" if (a.get("upsideNum") or 0) >= 0 else "#ff4d6d"
        sc_c = score_color(sc)

        price_html = f"""
            <div style='font-size:12px;color:#5a7099;margin-top:10px'>현재가</div>
            <div style='font-size:15px;font-weight:700;color:#fff'>{a.get('currentPrice', '–')}</div>
            <div style='font-size:10px;color:#3d5580'>{a.get('priceSource', '')}</div>"""

        badges_html = f"""
            <span class='ai-badge' style='background:{sc_c}20;color:{sc_c};border:1px solid {sc_c}40'>{sc}/10</span>
            <span class='ai-badge' style='background:{ud_c}20;color:{ud_c};border:1px solid {ud_c}40'>{a.get('upside', '–')}</span>
            <span class='ai-badge' style='background:{ac}20;color:{ac};border:1px solid {ac}40'>{act}</span>"""

        summary_html = f"<div style='font-size:11px;color:#7a8fa8;margin-top:8px;line-height:1.5'>{a.get('summary', '')}</div>"

    elif a and a.get("error"):
        summary_html = f"<div style='font-size:11px;color:#ff4d6d;margin-top:8px'>⚠ {a['error']}</div>"

    st.markdown(
        f"""
        <div class='ai-card'>
          <div style='position:absolute;top:0;left:0;right:0;height:3px;
                      background:linear-gradient(90deg,{bar_c} {bar_pct},#1a2540 {bar_pct})'></div>
          <div style='display:flex;justify-content:space-between;align-items:flex-start'>
            <div>
              <div style='font-size:15px;font-weight:700;color:#e8eaf0'>{stock['name']}</div>
              <div style='font-size:11px;color:#3d5580'>{stock['ticker']}</div>
            </div>
            <div style='text-align:right'>
              <div style='font-size:13px;font-weight:600;color:#7eb8ff'>{weight:.1f}%</div>
              <div style='font-size:11px;color:#3d5580'>₩{stock['amount'] // 10000:,}만</div>
            </div>
          </div>
          {book_html}{price_html}
          <div style='margin-top:10px'>{badges_html}</div>
          {summary_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── 섹션 5: 종목별 상세 분석 탭 ──────────────────────────────────────────────
def _render_detail_tabs(analyses: dict) -> None:
    analyzed = [
        s
        for s in PORTFOLIO
        if s["code"] in analyses and not analyses[s["code"]].get("error")
    ]
    if not analyzed:
        return

    st.divider()
    st.markdown("#### 종목별 상세 분석")

    for dtab, stock in zip(st.tabs([s["name"] for s in analyzed]), analyzed):
        with dtab:
            _render_single_detail(analyses[stock["code"]])


def _render_single_detail(a: dict) -> None:
    """종목 상세 분석 패널 1개 렌더링"""
    ud_val = a.get("upsideNum", 0) or 0
    ud_c = "#00e5a0" if ud_val >= 0 else "#ff4d6d"
    ed = a.get("earningsDirection", "–")
    ed_c = "#00e5a0" if ed == "우상향" else "#f5c518"

    # 상단 메트릭 4개
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재가", a.get("currentPrice", "–"), help=a.get("priceSource", ""))
    m2.metric("업사이드", a.get("upside", "–"))
    m3.metric("적정주가", a.get("fairPrice", "–"))
    m4.metric("매력도", f"{a.get('score', '–')}/10")
    st.divider()

    # 행 1: EPS / 밸류에이션
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        st.markdown("**📈 EPS 전망**")
        st.markdown(
            f"""
            <div class='ai-section'>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px'><span style='color:#5a7099'>2026E</span><span>{a.get('eps2026','–')}</span></div>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px'><span style='color:#5a7099'>2027E</span><span>{a.get('eps2027','–')}</span></div>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px'><span style='color:#5a7099'>2028E</span><span>{a.get('eps2028','–')}</span></div>
              <div style='display:flex;justify-content:space-between;font-size:12px;font-weight:700;margin-bottom:10px'><span style='color:#5a7099'>CAGR</span><span style='color:#fff'>{a.get('epsCagr','–')}</span></div>
              <div style='font-size:12px;color:#7a8fa8;line-height:1.6'>{a.get('growthDrivers','')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1c2:
        st.markdown("**💹 밸류에이션**")
        st.markdown(
            f"""
            <div class='ai-section'>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px'><span style='color:#5a7099'>역사적 PER</span><span>{a.get('historicalPer','–')}</span></div>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px'><span style='color:#5a7099'>적정 PER</span><span style='font-weight:700;color:#fff'>{a.get('fairPer','–')}배</span></div>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px'><span style='color:#5a7099'>적정주가</span><span style='font-weight:700;color:#fff'>{a.get('fairPrice','–')}</span></div>
              <div style='display:flex;justify-content:space-between;font-size:12px;margin-bottom:10px'><span style='color:#5a7099'>업사이드</span><span style='font-weight:700;color:{ud_c}'>{a.get('upside','–')}</span></div>
              <div style='font-size:12px;color:#7a8fa8;line-height:1.6'>{a.get('fairPerReason','')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 행 2: FCF & 뉴스 / 로드맵
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.markdown("**💰 FCF & 펀더멘털**")
        news_html = "".join(
            f"<div class='ai-news-item'>· {n}</div>"
            for n in (a.get("recentNews") or [])
        )
        st.markdown(
            f"""
            <div class='ai-section'>
              <div style='font-size:12px;color:#7a8fa8;line-height:1.6;margin-bottom:10px'>{a.get('fcfStatus','')}</div>
              <div style='font-size:11px;font-weight:600;color:#5a7099;margin-bottom:6px'>최근 핵심 뉴스</div>
              {news_html}
              <div style='margin-top:10px'>
                <span class='ai-badge' style='background:{ed_c}20;color:{ed_c};border:1px solid {ed_c}40'>실적방향: {ed}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2c2:
        st.markdown("**🗓 3개월 로드맵**")
        tl_html = ""
        for t in a.get("timeline") or []:
            dot_c = "#00e5a0" if t.get("type") == "opportunity" else "#ff4d6d"
            tl_html += f"""
            <div style='display:flex;gap:8px;margin-bottom:8px;align-items:flex-start'>
              <div style='width:8px;height:8px;border-radius:50%;background:{dot_c};margin-top:4px;flex-shrink:0'></div>
              <div>
                <div style='font-size:10px;color:#5a7099'>{t.get('date','')}</div>
                <div style='font-size:12px;color:#c8d0e0'>{t.get('event','')}</div>
              </div>
            </div>"""
        st.markdown(
            f"""
            <div class='ai-section'>
              {tl_html}
              <div style='padding:8px 10px;background:#00e5a010;border-radius:8px;border:1px solid #00e5a020;margin-top:8px'>
                <div style='font-size:10px;color:#00e5a0;font-weight:600;margin-bottom:4px'>⭐ 골든 타임</div>
                <div style='font-size:12px;color:#7a8fa8'>{a.get('goldenTime','')}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 행 3: 매매 신호 / 비교군
    r3c1, r3c2 = st.columns(2)
    with r3c1:
        st.markdown("**🚦 매매 신호**")
        st.markdown(
            f"""
            <div class='ai-section'>
              <div style='font-size:10px;color:#00e5a0;font-weight:600;margin-bottom:4px'>매수 확대 신호</div>
              <div style='font-size:12px;color:#7a8fa8;margin-bottom:12px'>{a.get('buySignal','')}</div>
              <div style='font-size:10px;color:#ff4d6d;font-weight:600;margin-bottom:4px'>매도/축소 신호</div>
              <div style='font-size:12px;color:#7a8fa8'>{a.get('sellSignal','')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r3c2:
        st.markdown("**🔍 비교군 브리핑**")
        st.markdown(
            f"""
            <div class='ai-section'>
              <div style='font-size:12px;color:#7a8fa8;line-height:1.7'>{a.get('peers','')}</div>
              <div style='font-size:11px;color:#5a7099;margin-top:10px'>경쟁사 PER 비교</div>
              <div style='font-size:12px;color:#c8d0e0;margin-top:4px'>{a.get('peerPer','')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── 섹션 6: 관리 필요 종목 ───────────────────────────────────────────────────
def _render_alerts(analyses: dict) -> None:
    alert_stocks = [
        (s, analyses[s["code"]])
        for s in PORTFOLIO
        if s["code"] in analyses
        and not analyses[s["code"]].get("error")
        and analyses[s["code"]].get("action") in _ALERT_ACTIONS
    ]
    if not alert_stocks:
        return

    st.divider()
    st.markdown("#### ⚠️ 관리 필요 종목")
    a_cols = st.columns(min(len(alert_stocks), 3))

    for i, (stock, a) in enumerate(alert_stocks):
        act = a.get("action", "")
        ac = ACTION_COLOR.get(act, "#aaa")
        with a_cols[i % 3]:
            st.markdown(
                f"""
                <div class='ai-alert' style='background:{ac}08;border:1px solid {ac}30'>
                  <div style='display:flex;justify-content:space-between;align-items:center'>
                    <span style='font-size:15px;font-weight:700;color:#e8eaf0'>{stock['name']}</span>
                    <span class='ai-badge' style='background:{ac}20;color:{ac};border:1px solid {ac}40'>{act}</span>
                  </div>
                  <div style='font-size:12px;color:#7a8fa8;margin-top:8px'>{a.get('summary','')}</div>
                  <div style='font-size:12px;color:{ac};margin-top:6px'>업사이드: {a.get('upside','–')} · 점수: {a.get('score','–')}/10</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ── 섹션 7: 예수금 활용 전략 ─────────────────────────────────────────────────
def _render_cash_strategy(analyses: dict) -> None:
    golden_stocks = [
        (s["name"], analyses[s["code"]].get("goldenTime", ""))
        for s in PORTFOLIO
        if s["code"] in analyses
        and not analyses[s["code"]].get("error")
        and analyses[s["code"]].get("action") in _GOLDEN_ACTIONS
    ]
    if not golden_stocks:
        return

    st.divider()
    st.markdown("#### 💵 예수금 활용 전략")
    st.caption(f"현재 예수금: ₩{CASH:,} — 최소 50%는 현금 유보 권장")

    for name, gt in golden_stocks:
        st.markdown(
            f"""
            <div style='padding:10px 14px;background:#00e5a010;border:1px solid #00e5a030;
                        border-radius:10px;margin-bottom:6px'>
              <span style='font-weight:700;color:#00e5a0'>{name}</span>
              <span style='font-size:12px;color:#7a8fa8;margin-left:10px'>{gt}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── 퍼블릭 진입점 ─────────────────────────────────────────────────────────────
def render_ai_tab(get_secret_fn) -> None:
    """
    AI 투자 비서 탭 전체 렌더링.
    main.py의 `with tab_ai:` 블록에서 호출합니다.

    Args:
        get_secret_fn: secrets.toml / 환경변수에서 값을 읽는 함수
                       시그니처: (key: str, default=None) -> str | None
    """
    _render_css()

    # 세션 초기화
    if "ai_analyses" not in st.session_state:
        st.session_state["ai_analyses"] = {}

    # API Key 확인
    api_key = get_secret_fn("ANTHROPIC_API_KEY")
    if not api_key:
        st.warning(
            "⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다. `.streamlit/secrets.toml` 또는 환경변수를 확인해주세요."
        )
        api_key = st.text_input(
            "또는 여기에 직접 입력:", type="password", key="ai_api_key_input"
        )
        if not api_key:
            return

    analyses = st.session_state["ai_analyses"]
    scores = [
        v["score"]
        for v in analyses.values()
        if isinstance(v.get("score"), (int, float))
    ]
    avg_score = sum(scores) / len(scores) if scores else None

    _render_header(avg_score)
    _render_analyze_button(api_key, analyses)
    st.divider()
    _render_stock_cards(api_key, analyses)
    _render_detail_tabs(analyses)
    _render_alerts(analyses)
    _render_cash_strategy(analyses)
