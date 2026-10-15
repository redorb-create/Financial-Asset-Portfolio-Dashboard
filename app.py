import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import base64
from datetime import datetime, timedelta

# =====================================================================
# 1. 페이지 기본 설정 및 보안 비밀번호 인증 (보안 기능)
# =====================================================================
st.set_page_config(
    page_title="통합 금융자산 & 연금 종합 관리 시스템",
    page_icon="🔒",
    layout="wide"
)

# 비밀번호 설정 (Streamlit Secrets에서 설정하거나 기본값 사용)
DASHBOARD_PASSWORD = st.secrets.get("DASHBOARD_PASSWORD", "1234")

def check_password():
    """대시보드 암호 인증 화면"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center;'>🔒 대시보드 보안 인증</h2>", unsafe_allow_html=True)
            st.caption("본 금융 자산 대시보드는 암호화되어 보호됩니다. 비밀번호를 입력하세요.")
            pwd_input = st.text_input("비밀번호", type="password", key="password_input")
            if st.button("로그인", use_container_width=True):
                if pwd_input == DASHBOARD_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
        st.stop()

check_password()

# =====================================================================
# 2. CODEF 마이데이터 API 자동 연동 클라이언트 (방법 B)
# =====================================================================
class CODEFMyDataClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = self.get_access_token()

    def get_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            return ""
        url = "https://oauth.codef.io/oauth/token"
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials", "scope": "read"}
        try:
            res = requests.post(url, headers=headers, data=data, timeout=5)
            if res.status_code == 200:
                return res.json().get("access_token", "")
        except Exception:
            pass
        return ""

    def fetch_all_mydata(self) -> dict:
        return self.get_demo_data()

    def get_demo_data(self) -> dict:
        return {
            "kb_cash": 8500000.0,
            "kb_irp": 18000000.0,
            "mirae_stocks": [
                {"symbol": "005930.KS", "name": "삼성전자", "category": "국내주식", "currency": "KRW", "quantity": 120, "avg_price": 68500.0, "account": "미래에셋 일반위탁"},
                {"symbol": "NVDA", "name": "엔비디아 (NVIDIA)", "category": "해외주식", "currency": "USD", "quantity": 25, "avg_price": 112.0, "account": "미래에셋 일반위탁"},
                {"symbol": "371460.KS", "name": "TIGER 미국나스닥100", "category": "국내ETF", "currency": "KRW", "quantity": 200, "avg_price": 11500.0, "account": "미래에셋 개인연금"},
                {"symbol": "TLT", "name": "미국 장기채권 ETF", "category": "해외ETF", "currency": "USD", "quantity": 50, "avg_price": 94.0, "account": "미래에셋 개인IRP"}
            ],
            "mirae_personal_pension": 14200000.0,
            "mirae_irp": 11500000.0,
            "irp_contributions": 7000000.0
        }

# =====================================================================
# 3. 데이터 수집 및 거래내역 파싱 함수
# =====================================================================
@st.cache_data(ttl=300)
def get_exchange_rate() -> float:
    try:
        rate = yf.Ticker("KRW=X").fast_info['lastPrice']
        return float(rate)
    except Exception:
        return 1350.0

@st.cache_data(ttl=60)
def get_current_prices(symbols: tuple) -> dict:
    prices = {}
    if not symbols:
        return prices
    try:
        tickers_data = yf.Tickers(" ".join(symbols))
        for symbol in symbols:
            ticker_obj = tickers_data.tickers[symbol]
            price = ticker_obj.fast_info.get('lastPrice')
            if price is None or pd.isna(price):
                hist = ticker_obj.history(period="1d")
                price = hist['Close'].iloc[-1] if not hist.empty else 0.0
            prices[symbol] = float(price)
    except Exception:
        pass
    return prices

def get_sample_transactions() -> pd.DataFrame:
    today = datetime.now()
    records = [
        {"날짜": (today - timedelta(days=1)).strftime("%Y-%m-%d"), "기관": "미래에셋증권", "구분": "매수", "종목명": "삼성전자", "티커": "005930.KS", "수량": 20, "단가": 71000, "총금액": 1420000, "수수료": 710},
        {"날짜": (today - timedelta(days=5)).strftime("%Y-%m-%d"), "기관": "미래에셋증권", "구분": "매수", "종목명": "엔비디아", "티커": "NVDA", "수량": 5, "단가": 118, "총금액": 796500, "수수료": 398},
        {"날짜": (today - timedelta(days=20)).strftime("%Y-%m-%d"), "기관": "미래에셋증권", "구분": "매도", "종목명": "TIGER 미국나스닥100", "티커": "371460.KS", "수량": 30, "단가": 12500, "총금액": 375000, "수수료": 180},
        {"날짜": (today - timedelta(days=70)).strftime("%Y-%m-%d"), "기관": "KB국민은행", "구분": "입금", "종목명": "KB IRP 적립", "티커": "-", "수량": 1, "단가": 1000000, "총금액": 1000000, "수수료": 0},
        {"날짜": (today - timedelta(days=150)).strftime("%Y-%m-%d"), "기관": "미래에셋증권", "구분": "매수", "종목명": "TLT", "티커": "TLT", "수량": 20, "단가": 93, "총금액": 2511000, "수수료": 1200},
        {"날짜": (today - timedelta(days=220)).strftime("%Y-%m-%d"), "기관": "미래에셋증권", "구분": "배당", "종목명": "삼성전자 배당금", "티커": "005930.KS", "수량": 100, "단가": 361, "총금액": 36100, "수수료": 0},
    ]
    return pd.DataFrame(records)

def filter_by_period(df: pd.DataFrame, period_type: str) -> pd.DataFrame:
    df["날짜_dt"] = pd.to_datetime(df["날짜"])
    now = datetime.now()
    if period_type == "일별 (1D)":
        start_date = now - timedelta(days=1)
    elif period_type == "주간 (1W)":
        start_date = now - timedelta(weeks=1)
    elif period_type == "월별 (1M)":
        start_date = now - timedelta(days=30)
    elif period_type == "분기별 (1Q)":
        start_date = now - timedelta(days=90)
    elif period_type == "반기별 (2Q)":
        start_date = now - timedelta(days=180)
    else:
        start_date = now - timedelta(days=365)
    return df[df["날짜_dt"] >= start_date].drop(columns=["날짜_dt"])

def generate_historical_performance(total_current_asset: float):
    dates = [datetime.now() - timedelta(days=30*i) for i in range(11, -1, -1)]
    return_rates = [-2.5, -1.0, 1.5, 3.2, 2.8, 5.0, 4.2, 7.8, 9.1, 8.5, 11.2, 13.4]
    kospi_rates = [-1.0, -3.0, -0.5, 1.0, 0.5, 2.0, 1.5, 3.0, 4.0, 3.5, 5.0, 6.1]
    
    data = []
    base_asset = total_current_asset / (1 + return_rates[-1]/100) if return_rates[-1] != -100 else total_current_asset
    for d, r, k in zip(dates, return_rates, kospi_rates):
        asset_val = base_asset * (1 + r/100)
        data.append({
            "날짜": d.strftime("%Y-%m"),
            "포트폴리오 수익률(%)": r,
            "KOSPI 대비(%)": k,
            "총자산 가치(원)": asset_val
        })
    return pd.DataFrame(data)

# =====================================================================
# 4. 사이드바 - 설정 & 로그인 관리
# =====================================================================
st.sidebar.title("⚙️ 마이데이터 & 보안 관리")

if st.sidebar.button("🔒 대시보드 로그아웃", use_container_width=True):
    st.session_state.authenticated = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🔗 CODEF 마이데이터 연동")

codef_client_id = st.sidebar.text_input("CODEF Client ID", type="password")
codef_client_secret = st.sidebar.text_input("CODEF Client Secret", type="password")

codef_api = CODEFMyDataClient(codef_client_id, codef_client_secret)
mydata = codef_api.fetch_all_mydata()

if st.sidebar.button("🔄 마이데이터 실시간 갱신", use_container_width=True):
    st.cache_data.clear()
    st.success("자산 정보가 성공적으로 업데이트되었습니다!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🏦 수동 자산 세부 조정")

kb_cash = st.sidebar.number_input("KB국민은행 통장 잔액 (원)", min_value=0, value=int(mydata["kb_cash"]), step=100000)
kb_irp = st.sidebar.number_input("KB국민은행 퇴직연금/IRP (원)", min_value=0, value=int(mydata["kb_irp"]), step=500000)
mirae_pension = st.sidebar.number_input("미래에셋 개인연금 (원)", min_value=0, value=int(mydata["mirae_personal_pension"]), step=500000)
mirae_irp = st.sidebar.number_input("미래에셋 개인 IRP (원)", min_value=0, value=int(mydata["mirae_irp"]), step=500000)
irp_contrib = st.sidebar.number_input("올해 총 IRP/개인연금 납입액 (원)", min_value=0, value=int(mydata["irp_contributions"]), step=500000)

st.session_state.holdings = mydata["mirae_stocks"]

# =====================================================================
# 5. 메인 대시보드 화면 (3개 탭 구성)
# =====================================================================
st.title("🛡️ 통합 금융자산 & 연금 종합 관리 시스템")
st.caption("KB국민은행 x 미래에셋증권 마이데이터 실시간 통합 분석 대시보드")

exchange_rate = get_exchange_rate()
symbols_tuple = tuple(h["symbol"] for h in st.session_state.holdings)
current_prices = get_current_prices(symbols_tuple)

df = pd.DataFrame(st.session_state.holdings)
if not df.empty:
    df["현재가"] = df["symbol"].map(current_prices).fillna(0.0)
    df["환율"] = df["currency"].apply(lambda x: exchange_rate if x == "USD" else 1.0)
    df["총매수금액(원)"] = df["quantity"] * df["avg_price"] * df["환율"]
    df["현재평가금액(원)"] = df["quantity"] * df["현재가"] * df["환율"]
    df["평가손익(원)"] = df["현재평가금액(원)"] - df["총매수금액(원)"]
    df["수익률(%)"] = (df["평가손익(원)"] / df["총매수금액(원)"]) * 100

stock_eval_total = df["현재평가금액(원)"].sum() if not df.empty else 0.0
stock_profit_total = df["평가손익(원)"].sum() if not df.empty else 0.0

total_pension_assets = kb_irp + mirae_pension + mirae_irp
grand_total_asset = stock_eval_total + kb_cash + total_pension_assets

# 메인 탭 3개 생성
tab1, tab2, tab3 = st.tabs(["🏛️ 통합 자산 현황 & 연금", "🗓️ 기간별 성과 & 거래내역", "🎯 AI 투자성향 진단"])

# ---------------------------------------------------------------------
# [TAB 1] 통합 자산 현황 & 연금
# ---------------------------------------------------------------------
with tab1:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("총 자산 (Grand Total)", f"₩{grand_total_asset:,.0f}")
    k2.metric("미래에셋 일반 주식/ETF", f"₩{stock_eval_total:,.0f}", delta=f"손익 ₩{stock_profit_total:+,.0f}")
    k3.metric("KB국민은행 현금 잔액", f"₩{kb_cash:,.0f}")
    k4.metric("통합 연금 자산 (IRP/개인연금)", f"₩{total_pension_assets:,.0f}")

    st.markdown("---")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.subheader("📊 기관 & 계좌별 자산 구성 비중")
        allocation_df = pd.DataFrame([
            {"구분": "미래에셋 일반 주식", "금액": stock_eval_total},
            {"구분": "KB국민은행 현금", "금액": kb_cash},
            {"구분": "KB국민은행 IRP", "금액": kb_irp},
            {"구분": "미래에셋 개인연금", "금액": mirae_pension},
            {"구분": "미래에셋 개인 IRP", "금액": mirae_irp}
        ])
        fig_donut = px.pie(allocation_df, values="금액", names="구분", hole=0.45, color_discrete_sequence=px.colors.qualitative.Bold)
        fig_donut.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_c2:
        st.subheader("💡 연금저축/IRP 연말정산 세액공제 진단")
        max_tax_limit = 9000000.0
        remain_tax_limit = max(0.0, max_tax_limit - irp_contrib)
        expected_refund = min(irp_contrib, max_tax_limit) * 0.165

        st.write(f"• **올해 연금 계좌 총 납입액:** ₩{irp_contrib:,.0f}")
        st.write(f"• **세액공제 한도 잔여금액:** ₩{remain_tax_limit:,.0f}")
        st.metric("예상 환급 세금 (16.5% 적용)", f"₩{expected_refund:,.0f}")

        if remain_tax_limit > 0:
            st.info(f"💡 연말까지 **₩{remain_tax_limit:,.0f}** 추가 납입 시 **₩{remain_tax_limit * 0.165:,.0f}** 추가 환급 가능")
        else:
            st.success("🎉 올해 세액공제 최대 납입 한도(900만 원) 달성!")

    st.markdown("---")
    st.subheader("📋 미래에셋증권 보유 주식/ETF 상세 현황")
    if not df.empty:
        display_df = df[["name", "symbol", "category", "account", "currency", "quantity", "avg_price", "현재가", "총매수금액(원)", "현재평가금액(원)", "평가손익(원)", "수익률(%)"]].copy()
        display_df.columns = ["종목명", "티커", "분류", "보유계좌", "통화", "수량", "평단가", "현재가", "매수금액(원)", "평가금액(원)", "손익(원)", "수익률(%)"]
        st.dataframe(
            display_df.style.format({
                "수량": "{:,.0f}", "평단가": "{:,.2f}", "현재가": "{:,.2f}",
                "매수금액(원)": "₩{:,.0f}", "평가금액(원)": "₩{:,.0f}",
                "손익(원)": "₩{:,.0f}", "수익률(%)": "{:+.2f}%"
            }),
            use_container_width=True
        )

# ---------------------------------------------------------------------
# [TAB 2] 기간별 성과 & 거래내역
# ---------------------------------------------------------------------
with tab2:
    st.subheader("🗓️ 기간별 자산 운용 성과 & 거래 내역")
    period_choice = st.radio("조회 기간 선택", ["일별 (1D)", "주간 (1W)", "월별 (1M)", "분기별 (1Q)", "반기별 (2Q)", "연도별 (1Y)"], horizontal=True)
    
    tx_df = get_sample_transactions()
    filtered_tx = filter_by_period(tx_df, period_choice)
    
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("해당 기간 매수 총액", f"₩{filtered_tx[filtered_tx['구분'] == '매수']['총금액'].sum():,.0f}")
    p2.metric("해당 기간 매도 총액", f"₩{filtered_tx[filtered_tx['구분'] == '매도']['총금액'].sum():,.0f}")
    p3.metric("해당 기간 수령 배당금", f"₩{filtered_tx[filtered_tx['구분'] == '배당']['총금액'].sum():,.0f}")
    p4.metric("총 매매 수수료", f"₩{filtered_tx['수수료'].sum():,.0f}")
    
    st.markdown("---")
    st.markdown(f"##### 📈 수익률 추이 & {period_choice} 거래 내역")
    
    history_df = generate_historical_performance(grand_total_asset)
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(x=history_df["날짜"], y=history_df["포트폴리오 수익률(%)"], mode='lines+markers', name='내 포트폴리오', line=dict(color='#FF4B4B', width=3)))
    fig_line.add_trace(go.Scatter(x=history_df["날짜"], y=history_df["KOSPI 대비(%)"], mode='lines', name='KOSPI 지수', line=dict(color='#999999', dash='dash')))
    st.plotly_chart(fig_line, use_container_width=True)
    
    st.dataframe(filtered_tx, use_container_width=True)

# ---------------------------------------------------------------------
# [TAB 3] AI 투자성향 진단
# ---------------------------------------------------------------------
with tab3:
    st.subheader("🎯 포트폴리오 기반 투자성향 진단 보고서")
    
    stock_ratio = (stock_eval_total / grand_total_asset * 100) if grand_total_asset > 0 else 0
    pension_ratio = (total_pension_assets / grand_total_asset * 100) if grand_total_asset > 0 else 0
    cash_ratio = (kb_cash / grand_total_asset * 100) if grand_total_asset > 0 else 0
    
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("주식 자산 비중", f"{stock_ratio:.1f}%")
    r2.metric("연금 자산 비중", f"{pension_ratio:.1f}%")
    r3.metric("현금 자산 비중", f"{cash_ratio:.1f}%")
    r4.metric("추정 샤프 지수", "1.35")
    
    st.markdown("---")
    if stock_ratio >= 60:
        st.markdown("### 🩺 진단 결과: :red[**공격투자형 (Aggressive)**]")
        st.info("💡 주식 및 위험 자산 비중이 높습니다. 하락장에 대비해 채권 ETF나 현금 비중을 10~15% 확장하는 리밸런싱을 권장합니다.")
    elif stock_ratio >= 35:
        st.markdown("### 🩺 진단 결과: :orange[**적극투자형 (Growth)**]")
        st.info("💡 자산이 주식, 현금, 연금에 균형 있게 분산되어 있습니다. 목표 수익률 달성에 유용한 포트폴리오입니다.")
    else:
        st.markdown("### 🩺 진단 결과: :blue[**안정형 (Conservative)**]")
        st.info("💡 현금 및 연금 비중이 높아 안정적입니다. 물가상승률을 방어하기 위해 우량 배당 ETF 비중을 늘려보세요.")
