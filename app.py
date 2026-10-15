import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go

# =====================================================================
# 1. 페이지 기본 설정
# =====================================================================
st.set_page_config(
    page_title="실시간 자산 관리 대시보드",
    page_icon="📈",
    layout="wide"
)

# 세션 상태 초기화 (기본 종목 데이터 세팅)
if "holdings" not in st.session_state:
    st.session_state.holdings = [
        {"symbol": "005930.KS", "name": "삼성전자", "category": "국내주식", "currency": "KRW", "quantity": 100, "avg_price": 68000.0},
        {"symbol": "NVDA", "name": "엔비디아 (NVIDIA)", "category": "해외주식", "currency": "USD", "quantity": 20, "avg_price": 115.0},
        {"symbol": "371460.KS", "name": "TIGER 미국나스닥100", "category": "국내ETF", "currency": "KRW", "quantity": 150, "avg_price": 11200.0},
        {"symbol": "TLT", "name": "미국 장기채권 ETF", "category": "해외ETF", "currency": "USD", "quantity": 40, "avg_price": 95.5}
    ]

# =====================================================================
# 2. 실시간 데이터 캐싱 수집 함수 (성능 최적화)
# =====================================================================
@st.cache_data(ttl=300)  # 5분 간격 캐싱
def get_exchange_rate() -> float:
    """실시간 USD/KRW 환율 조회"""
    try:
        ticker = yf.Ticker("KRW=X")
        rate = ticker.fast_info['lastPrice']
        return float(rate)
    except Exception:
        return 1350.0  # 오류 시 기본값

@st.cache_data(ttl=60)  # 1분 간격 캐싱
def get_current_prices(symbols: tuple) -> dict:
    """yfinance를 통한 종목별 실시간 현재가 일괄 조회"""
    prices = {}
    if not symbols:
        return prices
    try:
        tickers_data = yf.Tickers(" ".join(symbols))
        for symbol in symbols:
            ticker_obj = tickers_data.tickers[symbol]
            current_price = ticker_obj.fast_info.get('lastPrice')
            if current_price is None or pd.isna(current_price):
                hist = ticker_obj.history(period="1d")
                current_price = hist['Close'].iloc[-1] if not hist.empty else 0.0
            prices[symbol] = float(current_price)
    except Exception as e:
        st.error(f"주가 정보를 가져오는 중 오류 발생: {e}")
    return prices

# =====================================================================
# 3. 데이터 계산 및 메인 화면 구현
# =====================================================================
st.title("📈 개인 투자자산 실시간 포트폴리오 대시보드")
st.caption("yfinance 기반 실시간 주가 및 환율 정보 자동 업데이트")

# 실시간 환율 및 주가 가져오기
exchange_rate = get_exchange_rate()
symbols_tuple = tuple(h["symbol"] for h in st.session_state.holdings)
current_prices = get_current_prices(symbols_tuple)

# 데이터프레임 생성 및 손익 계산
df = pd.DataFrame(st.session_state.holdings)

if not df.empty:
    df["현재가"] = df["symbol"].map(current_prices).fillna(0.0)
    df["환율"] = df["currency"].apply(lambda x: exchange_rate if x == "USD" else 1.0)
    
    df["총매수금액(원)"] = df["quantity"] * df["avg_price"] * df["환율"]
    df["현재평가금액(원)"] = df["quantity"] * df["현재가"] * df["환율"]
    df["평가손익(원)"] = df["현재평가금액(원)"] - df["총매수금액(원)"]
    df["수익률(%)"] = (df["평가손익(원)"] / df["총매수금액(원)"]) * 100
    
    total_eval = df["현재평가금액(원)"].sum()
    df["자산비중(%)"] = (df["현재평가금액(원)"] / total_eval * 100) if total_eval > 0 else 0.0

    # Key Metrics (핵심 지표 상단 표시)
    total_invested = df["총매수금액(원)"].sum()
    total_profit = df["현재평가금액(원)"].sum() - total_invested
    total_return_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 평가 자산", f"₩{total_eval:,.0f}")
    m2.metric("총 투자 원금", f"₩{total_invested:,.0f}")
    m3.metric("누적 평가 손익", f"₩{total_profit:+,.0f}", delta=f"{total_return_pct:+.2f}%")
    m4.metric("적용 환율 (USD/KRW)", f"₩{exchange_rate:,.2f}")

    st.markdown("---")

    # 대시보드 시각화 (차트)
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("📊 카테고리별 자산 비중")
        fig_pie = px.pie(
            df, 
            values="현재평가금액(원)", 
            names="name", 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_chart2:
        st.subheader("💵 종목별 평가 손익 (원)")
        # 한국 금융시장 표준 색상 (수익: 빨강, 손실: 파랑)
        colors = ['#FF4B4B' if val >= 0 else '#4B89DC' for val in df["평가손익(원)"]]
        fig_bar = go.Figure(data=[
            go.Bar(
                x=df["name"], 
                y=df["평가손익(원)"],
                marker_color=colors,
                text=[f"₩{val:+,.0f}" for val in df["평가손익(원)"]],
                textposition='auto'
            )
        ])
        fig_bar.update_layout(xaxis_title="종목명", yaxis_title="손익 (원)", showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # 상세 자산 리스트 테이블
    st.subheader("📋 보유 종목 상세 현황")
    
    display_df = df[[
        "name", "symbol", "category", "currency", "quantity", 
        "avg_price", "현재가", "총매수금액(원)", "현재평가금액(원)", "평가손익(원)", "수익률(%)", "자산비중(%)"
    ]].copy()
    
    display_df.columns = [
        "종목명", "티커", "분류", "통화", "수량", 
        "평단가", "현재가", "매수금액(원)", "평가금액(원)", "손익(원)", "수익률(%)", "비중(%)"
    ]
    
    st.dataframe(
        display_df.style.format({
            "수량": "{:,.0f}",
            "평단가": "{:,.2f}",
            "현재가": "{:,.2f}",
            "매수금액(원)": "₩{:,.0f}",
            "평가금액(원)": "₩{:,.0f}",
            "손익(원)": "₩{:,.0f}",
            "수익률(%)": "{:+.2f}%",
            "비중(%)": "{:.1f}%"
        }),
        use_container_width=True
    )

# =====================================================================
# 4. 사이드바 - 종목 추가/삭제/수정
# =====================================================================
with st.sidebar:
    st.header("⚙️ 포트폴리오 관리")
    
    # 1) 종목 추가
    with st.expander("➕ 새 종목 추가", expanded=False):
        with st.form("add_symbol_form"):
            new_symbol = st.text_input("티커 (예: 005930.KS, AAPL)", value="AAPL")
            new_name = st.text_input("종목명", value="애플 (Apple)")
            new_category = st.selectbox("분류", ["국내주식", "해외주식", "국내ETF", "해외ETF", "채권", "암호화폐"])
            new_currency = st.selectbox("통화", ["USD", "KRW"])
            new_quantity = st.number_input("보유 수량", min_value=1, value=10)
            new_avg_price = st.number_input("평단가 (선택 통화 기준)", min_value=0.0, value=220.0)
            
            submit_btn = st.form_submit_button("종목 추가하기")
            if submit_btn:
                st.session_state.holdings.append({
                    "symbol": new_symbol.strip(),
                    "name": new_name.strip(),
                    "category": new_category,
                    "currency": new_currency,
                    "quantity": int(new_quantity),
                    "avg_price": float(new_avg_price)
                })
                st.cache_data.clear()  # 캐시 삭제 후 리프레시
                st.success(f"{new_name} 종목이 추가되었습니다!")
                st.rerun()

    # 2) 종목 삭제
    with st.expander("🗑️ 종목 삭제", expanded=False):
        if st.session_state.holdings:
            del_target = st.selectbox(
                "삭제할 종목 선택", 
                options=[h["name"] for h in st.session_state.holdings]
            )
            if st.button("선택 종목 삭제"):
                st.session_state.holdings = [
                    h for h in st.session_state.holdings if h["name"] != del_target
                ]
                st.cache_data.clear()
                st.success(f"{del_target} 삭제 완료!")
                st.rerun()
        else:
            st.write("삭제할 종목이 없습니다.")

    # 데이터 새로고침 버튼
    if st.button("🔄 실시간 시세 즉시 갱신"):
        st.cache_data.clear()
        st.rerun()