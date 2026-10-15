import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go

# =====================================================================
# 1. 페이지 기본 및 레이아웃 설정
# =====================================================================
st.set_page_config(
    page_title="KB x 미래에셋 통합 자산관리 대시보드",
    page_icon="💰",
    layout="wide"
)

# 세션 상태(Session State) 데이터 초기화
if "holdings" not in st.session_state:
    st.session_state.holdings = [
        {"symbol": "005930.KS", "name": "삼성전자", "category": "국내주식", "currency": "KRW", "quantity": 100, "avg_price": 68000.0, "broker": "미래에셋증권"},
        {"symbol": "NVDA", "name": "엔비디아 (NVIDIA)", "category": "해외주식", "currency": "USD", "quantity": 20, "avg_price": 115.0, "broker": "미래에셋증권"},
        {"symbol": "371460.KS", "name": "TIGER 미국나스닥100", "category": "국내ETF", "currency": "KRW", "quantity": 150, "avg_price": 11200.0, "broker": "미래에셋증권"},
        {"symbol": "TLT", "name": "미국 장기채권 ETF", "category": "해외ETF", "currency": "USD", "quantity": 40, "avg_price": 95.5, "broker": "미래에셋증권"}
    ]

if "kb_cash" not in st.session_state:
    st.session_state.kb_cash = 5000000.0  # KB국민은행 입출금 현금 잔액

if "kb_pension" not in st.session_state:
    st.session_state.kb_pension = {
        "total": 24500000.0,    # KB 퇴직연금/IRP 총 평가금액
        "contrib": 6000000.0,   # 올해 IRP 개인 납입액 (세액공제용)
        "type": "개인형 IRP"
    }

# =====================================================================
# 2. 실시간 데이터 캐싱 수집 함수 (yfinance)
# =====================================================================
@st.cache_data(ttl=300)
def get_exchange_rate() -> float:
    """실시간 USD/KRW 환율 조회"""
    try:
        ticker = yf.Ticker("KRW=X")
        rate = ticker.fast_info['lastPrice']
        return float(rate)
    except Exception:
        return 1350.0

@st.cache_data(ttl=60)
def get_current_prices(symbols: tuple) -> dict:
    """yfinance를 통한 주가/ETF 실시간 가격 일괄 조회"""
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
        st.error(f"주가 조회 중 오류 발생: {e}")
    return prices

def parse_mirae_asset_csv(uploaded_file) -> list:
    """미래에셋증권 M-STOCK / HTS 거래내역 CSV 파싱"""
    try:
        try:
            df = pd.read_csv(uploaded_file, encoding="euc-kr")
        except UnicodeDecodeError:
            df = pd.read_csv(uploaded_file, encoding="utf-8")
        
        parsed_holdings = []
        for _, row in df.iterrows():
            parsed_holdings.append({
                "symbol": str(row.get("종목코드", row.get("티커", "005930.KS"))),
                "name": str(row.get("종목명", "미래에셋 보유종목")),
                "category": "국내주식" if str(row.get("종목코드", "")).endswith(".KS") else "해외주식",
                "currency": "USD" if str(row.get("통화", "KRW")) == "USD" else "KRW",
                "quantity": int(row.get("체결수량", row.get("수량", 10))),
                "avg_price": float(row.get("체결단가", row.get("평단가", 10000))),
                "broker": "미래에셋증권"
            })
        return parsed_holdings
    except Exception as e:
        st.error(f"미래에셋 CSV 파싱 실패: {e}")
        return []

# =====================================================================
# 3. 사이드바 - 계좌별 연동 관리 (KB국민은행 & 미래에셋증권)
# =====================================================================
st.sidebar.title("⚙️ 금융기관 계좌 연동")

# [1] KB국민은행 연동
with st.sidebar.expander("🟡 KB국민은행 (현금/예금)", expanded=True):
    kb_balance_input = st.number_input(
        "KB국민은행 통장 잔액 (원)", 
        min_value=0, 
        value=int(st.session_state.kb_cash), 
        step=100000
    )
    st.session_state.kb_cash = float(kb_balance_input)

# [2] KB국민은행 퇴직연금 연동
with st.sidebar.expander("🛡️ KB국민은행 퇴직연금 (IRP)", expanded=True):
    p_type = st.selectbox("연금 유형", ["개인형 IRP", "기업형 DC", "기업형 DB"])
    p_total = st.number_input("퇴직연금 총 평가금액 (원)", min_value=0, value=int(st.session_state.kb_pension["total"]), step=500000)
    p_contrib = st.number_input("올해 IRP 개인 납입액 (원)", min_value=0, value=int(st.session_state.kb_pension["contrib"]), step=500000)
    
    st.session_state.kb_pension = {
        "total": float(p_total),
        "contrib": float(p_contrib),
        "type": p_type
    }

# [3] 미래에셋증권 주식/ETF 연동
with st.sidebar.expander("🟠 미래에셋증권 (주식/ETF)", expanded=True):
    mirae_file = st.file_uploader("미래에셋 거래내역 CSV 파일", type=["csv"])
    if mirae_file is not None and st.button("미래에셋 내역 자동 반영"):
        mirae_data = parse_mirae_asset_csv(mirae_file)
        if mirae_data:
            st.session_state.holdings = mirae_data
            st.success(f"미래에셋 종목 {len(mirae_data)}개 수집 완료!")
            st.rerun()

    st.markdown("---")
    # 신규 종목 수동 추가
    with st.form("add_stock_form"):
        st.caption("➕ 종목 수동 추가")
        add_sym = st.text_input("티커 (예: AAPL, 005930.KS)", value="AAPL")
        add_name = st.text_input("종목명", value="애플")
        add_cat = st.selectbox("카테고리", ["해외주식", "국내주식", "국내ETF", "해외ETF"])
        add_curr = st.selectbox("통화", ["USD", "KRW"])
        add_qty = st.number_input("수량", min_value=1, value=10)
        add_price = st.number_input("평단가", min_value=0.0, value=220.0)
        if st.form_submit_button("종목 추가"):
            st.session_state.holdings.append({
                "symbol": add_sym.strip(), "name": add_name.strip(),
                "category": add_cat, "currency": add_curr,
                "quantity": int(add_qty), "avg_price": float(add_price),
                "broker": "미래에셋증권"
            })
            st.cache_data.clear()
            st.rerun()

if st.sidebar.button("🔄 실시간 시세 즉시 갱신"):
    st.cache_data.clear()
    st.rerun()

# =====================================================================
# 4. 메인 대시보드 - 데이터 계산 및 시각화
# =====================================================================
st.title("🏦 KB국민은행 x 미래에셋증권 통합 자산 대시보드")
st.caption("실시간 주가(yfinance), 환율, KB 현금/퇴직연금 자산 일괄 종합 보고서")

exchange_rate = get_exchange_rate()
symbols_tuple = tuple(h["symbol"] for h in st.session_state.holdings)
current_prices = get_current_prices(symbols_tuple)

# 주식/ETF 데이터 계산
df = pd.DataFrame(st.session_state.holdings)
if not df.empty:
    df["현재가"] = df["symbol"].map(current_prices).fillna(0.0)
    df["환율"] = df["currency"].apply(lambda x: exchange_rate if x == "USD" else 1.0)
    df["총매수금액(원)"] = df["quantity"] * df["avg_price"] * df["환율"]
    df["현재평가금액(원)"] = df["quantity"] * df["현재가"] * df["환율"]
    df["평가손익(원)"] = df["현재평가금액(원)"] - df["총매수금액(원)"]
    df["수익률(%)"] = (df["평가손익(원)"] / df["총매수금액(원)"]) * 100

stock_invested = df["총매수금액(원)"].sum() if not df.empty else 0.0
stock_evaluated = df["현재평가금액(원)"].sum() if not df.empty else 0.0
stock_profit = stock_evaluated - stock_invested

kb_cash_val = st.session_state.kb_cash
kb_pension_val = st.session_state.kb_pension["total"]

# 통합 총자산 계산
total_portfolio_asset = stock_evaluated + kb_cash_val + kb_pension_val

# Top Key Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("통합 총 자산", f"₩{total_portfolio_asset:,.0f}")
m2.metric("미래에셋 주식/ETF", f"₩{stock_evaluated:,.0f}", delta=f"손익 ₩{stock_profit:+,.0f}")
m3.metric("KB국민은행 현금", f"₩{kb_cash_val:,.0f}")
m4.metric("KB 퇴직연금 (IRP)", f"₩{kb_pension_val:,.0f}")

st.markdown("---")

# 차트 시각화
c1, c2 = st.columns(2)

with c1:
    st.subheader("📊 기관 및 자산군별 구성 비중")
    asset_allocation = pd.DataFrame([
        {"자산군": "미래에셋 주식/ETF", "금액": stock_evaluated},
        {"자산군": "KB국민은행 현금", "금액": kb_cash_val},
        {"자산군": "KB국민은행 퇴직연금", "금액": kb_pension_val}
    ])
    fig_donut = px.pie(
        asset_allocation, values="금액", names="자산군", hole=0.45,
        color_discrete_sequence=["#FF7A00", "#FFCC00", "#4A90E2"]
    )
    fig_donut.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_donut, use_container_width=True)

with c2:
    st.subheader("📈 미래에셋 보유 종목별 평가손익 (원)")
    if not df.empty:
        colors = ['#FF4B4B' if v >= 0 else '#4B89DC' for v in df["평가손익(원)"]]
        fig_bar = go.Figure(data=[
            go.Bar(
                x=df["name"], y=df["평가손익(원)"],
                marker_color=colors,
                text=[f"₩{v:+,.0f}" for v in df["평가손익(원)"]],
                textposition='auto'
            )
        ])
        fig_bar.update_layout(xaxis_title="종목명", yaxis_title="손익(원)", showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# 세액공제 절세 진단 섹션
st.subheader("💡 KB국민은행 IRP 연말정산 세액공제 진단")
irp_contrib = st.session_state.kb_pension["contrib"]
max_limit = 9000000.0
remain_limit = max(0.0, max_limit - irp_contrib)
tax_refund = min(irp_contrib, max_limit) * 0.165

col_t1, col_t2, col_t3 = st.columns(3)
col_t1.metric("올해 IRP 납입액", f"₩{irp_contrib:,.0f}")
col_t2.metric("추가 납입 가능 한도", f"₩{remain_limit:,.0f}")
col_t3.metric("예상 세금 환급액 (16.5%)", f"₩{tax_refund:,.0f}")

st.info(f"📌 올해 최대 세액공제 한도(900만 원)까지 **₩{remain_limit:,.0f}** 추가 납입 시 최대 **₩{remain_limit * 0.165:,.0f}**의 세금을 추가로 환급받을 수 있습니다.")

st.markdown("---")

# 상세보유 주식 테이블
st.subheader("📋 미래에셋증권 주식/ETF 상세 보유 현황")
if not df.empty:
    display_df = df[["name", "symbol", "category", "currency", "quantity", "avg_price", "현재가", "총매수금액(원)", "현재평가금액(원)", "평가손익(원)", "수익률(%)"]].copy()
    display_df.columns = ["종목명", "티커", "분류", "통화", "수량", "평단가", "현재가", "매수금액(원)", "평가금액(원)", "손익(원)", "수익률(%)"]
    
    st.dataframe(
        display_df.style.format({
            "수량": "{:,.0f}", "평단가": "{:,.2f}", "현재가": "{:,.2f}",
            "매수금액(원)": "₩{:,.0f}", "평가금액(원)": "₩{:,.0f}",
            "손익(원)": "₩{:,.0f}", "수익률(%)": "{:+.2f}%"
        }),
        use_container_width=True
    )
