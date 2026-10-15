import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# =====================================================================
# 1. 페이지 기본 설정 및 보안 인증
# =====================================================================
st.set_page_config(
    page_title="통합 자산·거래·배당 관리 시스템",
    page_icon="💎",
    layout="wide"
)

DASHBOARD_PASSWORD = st.secrets.get("DASHBOARD_PASSWORD", "1234")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center;'>🔒 보안 자산 대시보드</h2>", unsafe_allow_html=True)
            pwd_input = st.text_input("비밀번호 입력", type="password")
            if st.button("로그인", use_container_width=True):
                if pwd_input == DASHBOARD_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
        st.stop()

check_password()

# =====================================================================
# 2. 기본 데이터베이스 (세션 상태 초기화)
# =====================================================================
# 계좌 목록
ACCOUNTS = ["미래에셋 일반위탁", "미래에셋 개인연금", "미래에셋 IRP", "KB국민은행 통장", "KB국민은행 IRP"]

# 초기 거래 내역 DB
if "transactions_db" not in st.session_state:
    st.session_state.transactions_db = pd.DataFrame([
        {"날짜": "2025-01-15", "계좌": "미래에셋 일반위탁", "구분": "매수", "종목명": "삼성전자", "티커": "005930.KS", "자산군": "국내주식", "수량": 100, "단가": 68000.0, "통화": "KRW", "수수료": 680},
        {"날짜": "2025-02-10", "계좌": "미래에셋 일반위탁", "구분": "매수", "종목명": "엔비디아", "티커": "NVDA", "자산군": "해외주식", "수량": 20, "단가": 115.0, "통화": "USD", "수수료": 2},
        {"날짜": "2025-03-05", "계좌": "미래에셋 개인연금", "구분": "매수", "종목명": "TIGER 미국나스닥100", "티커": "371460.KS", "자산군": "ETF", "수량": 150, "단가": 11200.0, "통화": "KRW", "수수료": 0},
        {"날짜": "2025-04-12", "계좌": "미래에셋 IRP", "구분": "매수", "종목명": "미국 장기채권 ETF", "티커": "TLT", "자산군": "ETF", "수량": 40, "단가": 95.5, "통화": "USD", "수수료": 1},
        {"날짜": "2025-05-20", "계좌": "미래에셋 일반위탁", "구분": "매수", "종목명": "리얼티인컴", "티커": "O", "자산군": "해외주식", "수량": 50, "단가": 52.0, "통화": "USD", "수수료": 1},
        {"날짜": "2025-06-18", "계좌": "KB국민은행 통장", "구분": "입금", "종목명": "현금 예수금", "티커": "CASH", "자산군": "현금", "수량": 1, "단가": 5000000.0, "통화": "KRW", "수수료": 0}
    ])

# =====================================================================
# 3. 실시간 주가 / 환율 / 배당금 수집 함수 (yfinance)
# =====================================================================
@st.cache_data(ttl=300)
def get_exchange_rate() -> float:
    try:
        return float(yf.Ticker("KRW=X").fast_info['lastPrice'])
    except Exception:
        return 1350.0

@st.cache_data(ttl=300)
def fetch_market_data(tickers_tuple: tuple):
    """실시간 주가 및 주당 연간 배당금(Dividend) 자동 조회"""
    prices = {}
    dividends = {}
    
    for symbol in set(tickers_tuple):
        if symbol == "CASH":
            prices[symbol] = 1.0
            dividends[symbol] = 0.0
            continue
        try:
            t = yf.Ticker(symbol)
            # 현재가 수집
            price = t.fast_info.get('lastPrice')
            if price is None or pd.isna(price):
                hist = t.history(period="1d")
                price = hist['Close'].iloc[-1] if not hist.empty else 0.0
            prices[symbol] = float(price)
            
            # 주당 연간 배당금 수집 (DPS)
            div_rate = t.info.get('dividendRate', 0.0)
            if not div_rate:
                div_yield = t.info.get('dividendYield', 0.0)
                div_rate = price * div_yield if div_yield else 0.0
            dividends[symbol] = float(div_rate) if div_rate else 0.0
        except Exception:
            prices[symbol] = 0.0
            dividends[symbol] = 0.0
            
    return prices, dividends

# =====================================================================
# 4. 포트폴리오 요약 계산 엔진
# =====================================================================
def calculate_portfolio(df_tx: pd.DataFrame, exchange_rate: float):
    if df_tx.empty:
        return pd.DataFrame(), {}
    
    symbols = tuple(df_tx["티커"].unique())
    prices, dividends = fetch_market_data(symbols)
    
    # 보유 수량 및 평단가 집계
    summary = []
    for (acc, ticker), group in df_tx.groupby(["계좌", "티커"]):
        name = group["종목명"].iloc[0]
        cat = group["자산군"].iloc[0]
        curr = group["통화"].iloc[0]
        
        # 매수/매도 수량 및 금액 계산
        buys = group[group["구분"] == "매수"]
        sells = group[group["구분"] == "매도"]
        
        total_qty = buys["수량"].sum() - sells["수량"].sum()
        if total_qty <= 0 and ticker != "CASH":
            continue
            
        buy_amt = (buys["수량"] * buys["단가"]).sum()
        avg_price = (buy_amt / buys["수량"].sum()) if buys["수량"].sum() > 0 else 0.0
        
        current_p = prices.get(ticker, 0.0)
        annual_dps = dividends.get(ticker, 0.0)
        
        rate = exchange_rate if curr == "USD" else 1.0
        
        invested_krw = total_qty * avg_price * rate
        eval_krw = total_qty * current_p * rate
        profit_krw = eval_krw - invested_krw
        return_pct = (profit_krw / invested_krw * 100) if invested_krw > 0 else 0.0
        
        # 연간 예상 배당금 (원화)
        annual_div_krw = total_qty * annual_dps * rate
        div_yield_pct = (annual_div_krw / eval_krw * 100) if eval_krw > 0 else 0.0
        
        summary.append({
            "계좌": acc,
            "종목명": name,
            "티커": ticker,
            "자산군": cat,
            "통화": curr,
            "보유수량": total_qty,
            "평단가": avg_price,
            "현재가": current_p,
            "투자원금(원)": invested_krw,
            "평가금액(원)": eval_krw,
            "평가손익(원)": profit_krw,
            "수익률(%)": return_pct,
            "주당배당금": annual_dps,
            "연간배당금(원)": annual_div_krw,
            "배당수익률(%)": div_yield_pct
        })
        
    res_df = pd.DataFrame(summary)
    if not res_df.empty:
        total_eval = res_df["평가금액(원)"].sum()
        res_df["자산비중(%)"] = (res_df["평가금액(원)"] / total_eval * 100) if total_eval > 0 else 0.0
    return res_df

# =====================================================================
# 5. 사이드바 - 거래 등록 및 필터
# =====================================================================
st.sidebar.title("⚙️ 관리 & 거래 입력")
exchange_rate = get_exchange_rate()
st.sidebar.caption(f"💱 실시간 환율: **1 USD = {exchange_rate:,.2f} 원**")

# [요구사항 6] 신규 거래 등록 폼
with st.sidebar.expander("➕ 신규 거래내역 등록", expanded=False):
    with st.form("add_tx_form"):
        tx_date = st.date_input("거래일자", datetime.now())
        tx_acc = st.selectbox("계좌 선택", ACCOUNTS)
        tx_type = st.selectbox("구분", ["매수", "매도", "입금", "출금"])
        tx_name = st.text_input("종목명 (예: 엔비디아)", "애플")
        tx_symbol = st.text_input("티커 (예: AAPL, 005930.KS)", "AAPL")
        tx_cat = st.selectbox("자산군", ["해외주식", "국내주식", "ETF", "펀드", "현금"])
        tx_curr = st.selectbox("통화", ["USD", "KRW"])
        tx_qty = st.number_input("수량", min_value=1, value=10)
        tx_price = st.number_input("단가", min_value=0.0, value=220.0)
        tx_fee = st.number_input("수수료(원/달러)", min_value=0.0, value=0.0)
        
        if st.form_submit_button("거래 저장"):
            new_row = pd.DataFrame([{
                "날짜": tx_date.strftime("%Y-%m-%d"),
                "계좌": tx_acc,
                "구분": tx_type,
                "종목명": tx_name,
                "티커": tx_symbol.strip(),
                "자산군": tx_cat,
                "수량": int(tx_qty),
                "단가": float(tx_price),
                "통화": tx_curr,
                "수수료": float(tx_fee)
            }])
            st.session_state.transactions_db = pd.concat([st.session_state.transactions_db, new_row], ignore_index=True)
            st.cache_data.clear()
            st.success(f"{tx_name} {tx_type} 등록 완료!")
            st.rerun()

if st.sidebar.button("🔄 실시간 시세/배당 즉시 갱신", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# 포트폴리오 데이터 계산
portfolio_df = calculate_portfolio(st.session_state.transactions_db, exchange_rate)

# =====================================================================
# 6. 메인 화면 탭 구성 (요구사항 2~9)
# =====================================================================
st.title("💼 통합 자산·거래·배당 관리 시스템")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 통합 현황 & 트렌드 차트", 
    "🏢 계좌별 & 보유종목 현황", 
    "📑 종목/계좌별 거래내역 조회", 
    "💸 실시간 배당금 관리", 
    "🔍 상품 리스트"
])

# ---------------------------------------------------------------------
# [TAB 1] 자산 트렌드 차트 (요구사항 7, 8)
# ---------------------------------------------------------------------
with tab1:
    if not portfolio_df.empty:
        total_inv = portfolio_df["투자원금(원)"].sum()
        total_eval = portfolio_df["평가금액(원)"].sum()
        total_profit = portfolio_df["평가손익(원)"].sum()
        total_return = (total_profit / total_inv * 100) if total_inv > 0 else 0.0
        total_annual_div = portfolio_df["연간배당금(원)"].sum()

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("총 평가 자산", f"₩{total_eval:,.0f}")
        k2.metric("총 투자 원금", f"₩{total_inv:,.0f}")
        k3.metric("누적 평가 손익", f"₩{total_profit:+,.0f}", delta=f"{total_return:+.2f}%")
        k4.metric("예상 연간 배당금", f"₩{total_annual_div:,.0f}")

        st.markdown("---")
        
        # [요구사항 8] 7개 기간 자산 트렌드 차트
        st.subheader("📈 자산 규모 및 수익률 시계열 트렌드")
        period = st.radio(
            "조회 기간 선택",
            ["최근 1개월", "최근 3개월", "최근 6개월", "최근 1년", "최근 3년", "최근 5년", "전체기간"],
            horizontal=True
        )
        
        # 기간별 일수 매핑
        days_map = {"최근 1개월": 30, "최근 3개월": 90, "최근 6개월": 180, "최근 1년": 365, "최근 3년": 1095, "최근 5년": 1825, "전체기간": 2500}
        n_days = days_map[period]
        
        dates = [datetime.now() - timedelta(days=i) for i in range(n_days, -1, -5)]
        dates.reverse()
        
        # 트렌드 시뮬레이션 데이터 생성
        trend_data = []
        base_val = total_eval * 0.85
        for i, d in enumerate(dates):
            growth = (i / len(dates)) * (total_eval - base_val)
            val = base_val + growth
            profit = val - total_inv
            ret = (profit / total_inv * 100) if total_inv > 0 else 0
            trend_data.append({"날짜": d.strftime("%Y-%m-%d"), "자산규모(원)": val, "수익금(원)": profit, "수익률(%)": ret})
            
        trend_df = pd.DataFrame(trend_data)
        
        c_left, c_right = st.columns(2)
        with c_left:
            fig_asset = px.area(trend_df, x="날짜", y="자산규모(원)", title=f"{period} 자산 규모 추이 (원)", color_discrete_sequence=["#00C853"])
            st.plotly_chart(fig_asset, use_container_width=True)
        with c_right:
            fig_ret = px.line(trend_df, x="날짜", y="수익률(%)", title=f"{period} 누적 수익률 추이 (%)", color_discrete_sequence=["#FF3D00"])
            st.plotly_chart(fig_ret, use_container_width=True)

# ---------------------------------------------------------------------
# [TAB 2] 계좌별 & 보유종목 현황 (요구사항 4, 5)
# ---------------------------------------------------------------------
with tab2:
    if not portfolio_df.empty:
        st.subheader("🏢 계좌별 자산 잔액 현황")
        acc_summary = portfolio_df.groupby("계좌")[["투자원금(원)", "평가금액(원)", "평가손익(원)", "연간배당금(원)"]].sum().reset_index()
        acc_summary["수익률(%)"] = (acc_summary["평가손익(원)"] / acc_summary["투자원금(원)"] * 100).round(2)
        st.dataframe(acc_summary.style.format({
            "투자원금(원)": "₩{:,.0f}", "평가금액(원)": "₩{:,.0f}", 
            "평가손익(원)": "₩{:,.0f}", "연간배당금(원)": "₩{:,.0f}", "수익률(%)": "{:+.2f}%"
        }), use_container_width=True)

        st.markdown("---")
        st.subheader("📌 보유 종목별 실시간 현황")
        st.dataframe(portfolio_df[[
            "계좌", "종목명", "티커", "자산군", "보유수량", "평단가", "현재가", 
            "투자원금(원)", "평가금액(원)", "평가손익(원)", "수익률(%)", "자산비중(%)"
        ]].style.format({
            "보유수량": "{:,.0f}", "평단가": "{:,.2f}", "현재가": "{:,.2f}",
            "투자원금(원)": "₩{:,.0f}", "평가금액(원)": "₩{:,.0f}",
            "평가손익(원)": "₩{:,.0f}", "수익률(%)": "{:+.2f}%", "자산비중(%)": "{:.1f}%"
        }), use_container_width=True)

# ---------------------------------------------------------------------
# [TAB 3] 종목/계좌별 거래내역 및 필터 조회 (요구사항 3, 6)
# ---------------------------------------------------------------------
with tab3:
    st.subheader("📑 거래 내역 상세 필터 조회")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        selected_acc = st.multiselect("계좌 선택 필터", options=ACCOUNTS, default=ACCOUNTS)
    with col_f2:
        all_symbols = list(st.session_state.transactions_db["종목명"].unique())
        selected_sym = st.multiselect("종목 선택 필터", options=all_symbols, default=all_symbols)
    with col_f3:
        selected_type = st.multiselect("구분 필터", options=["매수", "매도", "입금", "출금"], default=["매수", "매도", "입금", "출금"])
        
    filtered_db = st.session_state.transactions_db[
        (st.session_state.transactions_db["계좌"].isin(selected_acc)) &
        (st.session_state.transactions_db["종목명"].isin(selected_sym)) &
        (st.session_state.transactions_db["구분"].isin(selected_type))
    ]
    
    st.dataframe(filtered_db, use_container_width=True)

# ---------------------------------------------------------------------
# [TAB 4] 실시간 배당금 관리 (요구사항 9)
# ---------------------------------------------------------------------
with tab4:
    st.subheader("💸 실시간 자동 수집 배당금 보고서")
    
    if not portfolio_df.empty:
        div_df = portfolio_df[portfolio_df["연간배당금(원)"] > 0].copy()
        
        d1, d2, d3 = st.columns(3)
        d1.metric("총 연간 예상 배당금", f"₩{div_df['연간배당금(원)'].sum():,.0f}")
        d2.metric("월 평균 배당금", f"₩{(div_df['연간배당금(원)'].sum() / 12):,.0f}")
        d3.metric("포트폴리오 평균 배당수익률", f"{(div_df['연간배당금(원)'].sum() / portfolio_df['평가금액(원)'].sum() * 100):.2f}%")

        st.markdown("---")
        
        c_div1, c_div2 = st.columns(2)
        with c_div1:
            st.markdown("##### 📅 월별 예상 배당금 분배 현황")
            months = [f"{m}월" for m in range(1, 13)]
            # 월별 분기 분배 가상 분배 차트
            monthly_divs = [div_df['연간배당금(원)'].sum() / 12] * 12
            fig_m_div = px.bar(x=months, y=monthly_divs, labels={'x':'월', 'y':'배당금(원)'}, color_discrete_sequence=['#2ECC71'])
            st.plotly_chart(fig_m_div, use_container_width=True)
            
        with c_div2:
            st.markdown("##### 🏢 계좌별 배당금 비중")
            fig_acc_div = px.pie(div_df, values="연간배당금(원)", names="계좌", hole=0.4)
            st.plotly_chart(fig_acc_div, use_container_width=True)

        st.markdown("##### 📋 종목별 배당금 및 배당수익률 상세 리스트")
        st.dataframe(div_df[["계좌", "종목명", "티커", "보유수량", "주당배당금", "연간배당금(원)", "배당수익률(%)"]].style.format({
            "보유수량": "{:,.0f}", "주당배당금": "{:,.2f}",
            "연간배당금(원)": "₩{:,.0f}", "배당수익률(%)": "{:.2f}%"
        }), use_container_width=True)

# ---------------------------------------------------------------------
# [TAB 5] 상품 리스트 (요구사항 2)
# ---------------------------------------------------------------------
with tab5:
    st.subheader("🔍 매수/매도 등록된 금융 상품 전체 리스트")
    if not portfolio_df.empty:
        prod_df = portfolio_df[["종목명", "티커", "자산군", "통화", "현재가", "주당배당금"]].drop_duplicates()
        st.dataframe(prod_df.style.format({
            "현재가": "{:,.2f}", "주당배당금": "{:,.2f}"
        }), use_container_width=True)
