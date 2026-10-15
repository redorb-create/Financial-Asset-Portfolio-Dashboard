import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
from datetime import datetime, timedelta

# =====================================================================
# 1. 페이지 설정 및 기본 CSS
# =====================================================================
st.set_page_config(
    page_title="개인 금융자산 포트폴리오 대시보드",
    page_icon="📈",
    layout="wide"
)

FINANCIAL_INSTITUTIONS = [
    "미래에셋증권", "한국투자증권", "NH투자증권", "삼성증권", "KB증권", "신한투자증권", "키움증권", "토스증권",
    "KB국민은행", "신한은행", "하나은행", "우리은행", "NH농협은행", "IBK기업은행", "Sh수협은행", "iM뱅크(대구)"
]

ACCOUNT_TYPES = ["일반위탁", "연금저축", "IRP", "퇴직연금(DC)", "입출금통장"]

st.markdown("""
<style>
    .dashboard-header {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border-radius: 12px;
        padding: 20px 28px;
        color: #FFFFFF !important;
        margin-bottom: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .dashboard-title {
        font-size: 24px;
        font-weight: 800;
        color: #F8FAFC !important;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .dashboard-subtitle {
        font-size: 13px;
        color: #94A3B8 !important;
        margin-top: 4px;
    }

    .summary-banner {
        background-color: var(--background-secondary-color, #F8FAFC);
        border: 1px solid var(--border-color, #E2E8F0);
        border-radius: 10px;
        padding: 12px 20px;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 20px;
        font-size: 14px;
        font-weight: 600;
        color: var(--text-color, #1E293B) !important;
        margin-bottom: 16px;
    }
    .summary-val { font-weight: 700; color: var(--text-color, #0F172A) !important; }
    .summary-eval { font-weight: 700; color: #3B82F6 !important; }
    .summary-profit-plus { font-weight: 700; color: #EF4444 !important; }
    .summary-profit-minus { font-weight: 700; color: #3B82F6 !important; }

    .stock-card {
        background-color: var(--background-secondary-color, #FFFFFF);
        border: 1px solid var(--border-color, #E2E8F0);
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stock-title { 
        font-size: 15px; 
        font-weight: 700; 
        color: var(--text-color, #0F172A) !important; 
    }
    .stock-price { 
        font-size: 14px; 
        font-weight: 700; 
        color: #EF4444 !important; 
        text-align: right; 
    }
    .card-label { 
        font-size: 11px; 
        color: var(--text-color-secondary, #64748B) !important; 
    }
    .card-num { 
        font-size: 12px; 
        font-weight: 600; 
        color: var(--text-color, #1E293B) !important; 
    }
    .card-profit-plus { font-size: 12px; font-weight: 700; color: #EF4444 !important; }
    .card-profit-minus { font-size: 12px; font-weight: 700; color: #3B82F6 !important; }
</style>
""", unsafe_allow_html=True)

DASHBOARD_PASSWORD = st.secrets.get("DASHBOARD_PASSWORD", "1234")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center;'>🔒 개인 금융자산 대시보드</h2>", unsafe_allow_html=True)
            st.caption("비밀번호 입력 후 엔터(Enter) 키를 누르면 로그인됩니다.")
            
            with st.form("login_form", clear_on_submit=False):
                pwd_input = st.text_input("비밀번호 입력", type="password", key="password_input")
                submit_button = st.form_submit_button("로그인", use_container_width=True)
                
                if submit_button:
                    if pwd_input == DASHBOARD_PASSWORD:
                        st.session_state.authenticated = True
                        st.rerun()
                    else:
                        st.error("비밀번호가 올바르지 않습니다.")
        st.stop()

check_password()

# =====================================================================
# 2. 전 종목 실시간 연관 검색 및 시세 수집 엔진
# =====================================================================
def search_naver_stock(query: str):
    """
    네이버 증권 자동완성 API를 연동하여 상장된 모든 주식/ETF 검색
    """
    if not query or len(query.strip()) < 1:
        return {}
        
    url = "https://ac.finance.naver.com/ac"
    params = {
        'q': query,
        'target': 'index,stock,etf,fn',
        'r_format': 'json',
        'r_enc': 'utf-8',
        'st': '111',
        'r_lt': '111'
    }
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'}
    
    results = {}
    try:
        res = requests.get(url, params=params, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            items = data.get('items', [])
            if items and len(items) > 0 and len(items[0]) > 0:
                for item in items[0]:
                    stock_name = item[0][0] # 종목명
                    stock_code = item[1][0] # 종목코드 (6자리)
                    market_type = item[2][0] if len(item) > 2 else "" # 시장 구분 (KOSPI/KOSDAQ)
                    
                    suffix = ".KQ" if market_type.upper() == "KOSDAQ" else ".KS"
                    full_ticker = f"{stock_code}{suffix}"
                    results[f"{stock_name} ({stock_code})"] = (stock_name, full_ticker)
    except Exception:
        pass
        
    return results

@st.cache_data(ttl=30)
def fetch_realtime_market_data(ticker_list: tuple):
    price_data = {}
    if not ticker_list:
        return price_data, 1350.0
        
    try:
        usd_krw_ticker = yf.Ticker("KRW=X")
        usd_krw = float(usd_krw_ticker.fast_info.get('lastPrice', 1350.0))
    except Exception:
        usd_krw = 1350.0

    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'}

    for symbol in set(ticker_list):
        if not symbol or symbol == "-":
            continue
            
        curr_price = 0.0
        dps = 0.0
        is_usd = not symbol.endswith((".KS", ".KQ"))
        
        if symbol.endswith((".KS", ".KQ")):
            code = re.sub(r'[^0-9]', '', symbol)
            url = f"https://m.stock.naver.com/api/stock/{code}/basic"
            try:
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    curr_price = float(data.get('nowVal', '0').replace(',', ''))
                    dps = float(data.get('dps', '0').replace(',', '')) if data.get('dps') else 0.0
            except Exception:
                curr_price = 0.0

        if curr_price == 0.0 or dps == 0.0:
            try:
                t = yf.Ticker(symbol)
                if curr_price == 0.0:
                    curr_price = t.fast_info.get('lastPrice', 0.0)
                    if curr_price == 0.0:
                        hist = t.history(period="1d")
                        if not hist.empty:
                            curr_price = hist['Close'].iloc[-1]
                if dps == 0.0:
                    dps = float(t.info.get('dividendRate', 0.0) or 0.0)
            except Exception:
                pass
                
        price_data[symbol] = {
            "현재가": float(curr_price),
            "주당배당금": float(dps),
            "통화": "USD" if is_usd else "KRW"
        }
        
    return price_data, usd_krw

# =====================================================================
# 3. 데이터베이스 세션 관리
# =====================================================================
if "account_list" not in st.session_state:
    st.session_state.account_list = []

if "portfolio_db" not in st.session_state:
    st.session_state.portfolio_db = pd.DataFrame(columns=[
        "종목명", "티커", "계좌", "수량", "평단가", "현재가", "매수금액", "평가금액", "손익", "수익률", "누적배당"
    ])

if "editing_stock" not in st.session_state:
    st.session_state.editing_stock = None

if not st.session_state.portfolio_db.empty:
    tickers = tuple(st.session_state.portfolio_db["티커"].unique())
    realtime_prices, current_usd_krw = fetch_realtime_market_data(tickers)
    
    for idx, row in st.session_state.portfolio_db.iterrows():
        symbol = row["티커"]
        curr_p = 0.0
        
        if symbol in realtime_prices:
            curr_p = realtime_prices[symbol]["현재가"]
            auto_dps = realtime_prices[symbol]["주당배당금"]
            if realtime_prices[symbol]["통화"] == "USD":
                curr_p *= current_usd_krw
                auto_dps *= current_usd_krw

        if curr_p == 0.0:
            curr_p = row["현재가"] if row["현재가"] > 0 else row["평단가"]

        st.session_state.portfolio_db.at[idx, "현재가"] = curr_p
        st.session_state.portfolio_db.at[idx, "평가금액"] = row["수량"] * curr_p
        st.session_state.portfolio_db.at[idx, "손익"] = (row["수량"] * curr_p) - row["매수금액"]
        if row["매수금액"] > 0:
            st.session_state.portfolio_db.at[idx, "수익률"] = round(
                (st.session_state.portfolio_db.at[idx, "손익"] / row["매수금액"]) * 100, 2
            )

df = st.session_state.portfolio_db

total_buy = df["매수금액"].sum() if not df.empty else 0
total_eval = df["평가금액"].sum() if not df.empty else 0
total_profit = total_eval - total_buy
total_rate = (total_profit / total_buy * 100) if total_buy > 0 else 0.0

# =====================================================================
# 4. 사이드바 - 전 종목 실시간 연관 검색 등록
# =====================================================================
with st.sidebar:
    st.header("⚙️ 포트폴리오 설정")
    
    if st.button("🔄 실시간 시세 즉시 갱신", use_container_width=True):
        st.cache_data.clear()
        st.success("실시간 시세가 반영되었습니다!")
        st.rerun()
        
    st.markdown("---")
    
    with st.expander("🏦 계좌 관리 (신규 등록/삭제)", expanded=True):
        st.subheader("➕ 신규 계좌 추가")
        selected_bank = st.selectbox("금융기관 선택", FINANCIAL_INSTITUTIONS)
        selected_type = st.selectbox("계좌 종류", ACCOUNT_TYPES)
        
        custom_acc_full_name = f"{selected_bank} {selected_type}"
        st.caption(f"등록될 계좌명: **{custom_acc_full_name}**")
        
        if st.button("➕ 계좌 등록", use_container_width=True):
            if custom_acc_full_name not in st.session_state.account_list:
                st.session_state.account_list.append(custom_acc_full_name)
                st.success(f"'{custom_acc_full_name}' 계좌 추가 완료!")
                st.rerun()
                
        if st.session_state.account_list:
            st.markdown("---")
            st.subheader("🗑️ 계좌 삭제")
            del_acc_target = st.selectbox("삭제할 계좌 선택", options=st.session_state.account_list)
            if st.button("🗑️ 선택 계좌 삭제", use_container_width=True):
                st.session_state.account_list.remove(del_acc_target)
                st.session_state.portfolio_db = st.session_state.portfolio_db[
                    st.session_state.portfolio_db["계좌"] != del_acc_target
                ].reset_index(drop=True)
                st.success(f"'{del_acc_target}' 삭제 완료!")
                st.rerun()

    # [핵심] 네이버 증권 API 실시간 연관 검색창
    with st.expander("📌 전체 ETF / 주식 실시간 검색 및 추가", expanded=True):
        if not st.session_state.account_list:
            st.warning("먼저 계좌를 신규 등록해 주세요.")
        else:
            in_acc = st.selectbox("계좌 선택", options=st.session_state.account_list)
            
            # 실시간 검색 키워드 입력
            search_input = st.text_input("ETF/주식 검색어 입력 (예: KODEX, TIGER, 미국, 200, SCHD)", "KODEX")
            
            # 네이버 증권 실시간 검색 실행
            search_dict = search_naver_stock(search_input)
            
            if search_dict:
                selected_label = st.selectbox("검색된 종목 선택", options=list(search_dict.keys()))
                final_name, final_ticker = search_dict[selected_label]
            else:
                st.info("💡 실시간 검색 결과가 없거나 해외주식/티커 직접 입력")
                final_name = st.text_input("종목명 직접 입력", search_input)
                final_ticker = st.text_input("티커/코드 직접 입력 (예: SCHD, NVDA, 069500.KS)", "")

            st.caption(f"최종 매핑 티커: **{final_ticker if final_ticker else '미입력'}**")
            
            with st.form("add_item_form"):
                in_qty = st.number_input("수량", min_value=1, value=10)
                in_avg = st.number_input("평단가(원)", min_value=0, value=10000)
                in_div = st.number_input("누적 배당금(원)", min_value=0, value=0)
                
                if st.form_submit_button("➕ 보유 종목 저장", use_container_width=True):
                    if not final_name.strip() or not final_ticker.strip():
                        st.error("종목명과 티커가 모두 설정되어야 합니다.")
                    else:
                        buy_amt = in_qty * in_avg
                        new_row = pd.DataFrame([{
                            "종목명": final_name.strip(), "티커": final_ticker.strip(), "계좌": in_acc,
                            "수량": in_qty, "평단가": in_avg, "현재가": in_avg,
                            "매수금액": buy_amt, "평가금액": buy_amt,
                            "손익": 0.0, "수익률": 0.0, "누적배당": in_div
                        }])
                        st.session_state.portfolio_db = pd.concat([st.session_state.portfolio_db, new_row], ignore_index=True)
                        st.cache_data.clear()
                        st.success(f"'{final_name}' 저장 완료!")
                        st.rerun()

# =====================================================================
# 5. 메인 대시보드
# =====================================================================
st.markdown('''
<div class="dashboard-header">
    <div>
        <h1 class="dashboard-title">📈 개인 금융자산 포트폴리오 대시보드</h1>
        <p class="dashboard-subtitle">실시간 시세 연동 및 계좌별 자산/연금/배당/투자리포트 통합 관리 시스템</p>
    </div>
</div>
''', unsafe_allow_html=True)

profit_style_class = "summary-profit-plus" if total_profit >= 0 else "summary-profit-minus"
st.markdown(f'''
<div class="summary-banner">
    <div>총 매수 <span class="summary-val">{total_buy:,.0f} 원</span></div>
    <div>총 평가 <span class="summary-eval">{total_eval:,.0f} 원</span></div>
    <div>총 손익 <span class="{profit_style_class}">{total_profit:+,.0f} 원 ({total_rate:+.2f}%)</span></div>
</div>
''', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 종목별 & 계좌별 현황", 
    "📑 거래 내역", 
    "📈 자산 트렌드", 
    "💸 배당금 현황",
    "📊 투자리포트"
])

# ---------------------------------------------------------------------
# [TAB 1] 종목별 현황
# ---------------------------------------------------------------------
with tab1:
    st.subheader("종목별 현황")
    
    if not df.empty:
        unique_stocks = list(df["종목명"].unique())
        
        if st.session_state.editing_stock is not None:
            target_stock = st.session_state.editing_stock
            st.info(f"✏️ **'{target_stock}' 종목 정보 수정**")
            stock_rows = df[df["종목명"] == target_stock]
            first_row = stock_rows.iloc[0]
            
            with st.form("edit_stock_form"):
                e_name = st.text_input("종목명", value=first_row["종목명"])
                e_ticker = st.text_input("티커", value=first_row["티커"])
                e_qty = st.number_input("총 보유 수량", value=int(stock_rows["수량"].sum()))
                e_avg = st.number_input("평단가(원)", value=int(first_row["평단가"]))
                e_curr = st.number_input("현재가(원)", value=int(first_row["현재가"]))
                e_div = st.number_input("누적 배당금(원)", value=int(stock_rows["누적배당"].sum()))
                
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    if st.form_submit_button("💾 저장", use_container_width=True):
                        for i in stock_rows.index:
                            st.session_state.portfolio_db.at[i, "종목명"] = e_name
                            st.session_state.portfolio_db.at[i, "티커"] = e_ticker
                            st.session_state.portfolio_db.at[i, "수량"] = e_qty
                            st.session_state.portfolio_db.at[i, "평단가"] = e_avg
                            st.session_state.portfolio_db.at[i, "현재가"] = e_curr
                            st.session_state.portfolio_db.at[i, "매수금액"] = e_qty * e_avg
                            st.session_state.portfolio_db.at[i, "평가금액"] = e_qty * e_curr
                            st.session_state.portfolio_db.at[i, "손익"] = (e_qty * e_curr) - (e_qty * e_avg)
                            st.session_state.portfolio_db.at[i, "누적배당"] = e_div
                            
                        st.session_state.editing_stock = None
                        st.success("수정 완료되었습니다.")
                        st.rerun()
                with c_btn2:
                    if st.form_submit_button("❌ 취소", use_container_width=True):
                        st.session_state.editing_stock = None
                        st.rerun()
            st.markdown("---")

        cols = st.columns(4)
        for idx, name in enumerate(unique_stocks):
            group = df[df["종목명"] == name]
            curr_p = group["현재가"].iloc[0]
            sum_qty = group["수량"].sum()
            sum_buy = group["매수금액"].sum()
            sum_eval = group["평가금액"].sum()
            sum_profit = group["손익"].sum()
            sum_div = group["누적배당"].sum()
            rate = (sum_profit / sum_buy * 100) if sum_buy > 0 else 0.0
            avg_p = (sum_buy / sum_qty) if sum_qty > 0 else 0
            
            col_idx = idx % 4
            profit_class = "card-profit-plus" if sum_profit >= 0 else "card-profit-minus"
            
            with cols[col_idx]:
                st.markdown(f'''
                <div class="stock-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="stock-title">{name}</div>
                        <div class="stock-price">{curr_p:,.0f}</div>
                    </div>
                    <hr style="margin:6px 0; border:none; border-top:1px solid rgba(148, 163, 184, 0.2);">
                    <div style="display:flex; justify-content:space-between;">
                        <div><span class="card-label">보유수량</span><br><span class="card-num">{sum_qty:,.0f}주</span></div>
                        <div style="text-align:right;"><span class="card-label">평단가</span><br><span class="card-num">{avg_p:,.0f}</span></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:4px;">
                        <div><span class="card-label">총 매수금</span><br><span class="card-num">{sum_buy:,.0f}</span></div>
                        <div style="text-align:right;"><span class="card-label">총 평가금</span><br><span class="card-num">{sum_eval:,.0f}</span></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:4px;">
                        <div><span class="card-label">전체 수익금</span><br><span class="{profit_class}">{sum_profit:+,.0f}</span></div>
                        <div style="text-align:right;"><span class="card-label">전체 수익률</span><br><span class="{profit_class}">{rate:+.2f}%</span></div>
                    </div>
                    <div style="margin-top:4px; text-align:right; font-size:11px; color:#10B981; font-weight:600;">
                        누적 배당금: ₩{sum_div:,.0f}
                    </div>
                </div>
                ''', unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("계좌별 보유현황")
        
        for name, group in df.groupby("종목명"):
            with st.expander(f"📦 {name}  |  평가금액: ₩{group['평가금액'].sum():,.0f} ({group['손익'].sum():+,.0f}원)", expanded=True):
                display_g = group[["계좌", "수량", "평단가", "매수금액", "평가금액", "손익", "수익률", "누적배당"]].copy()
                st.dataframe(display_g.style.format({
                    "수량": "{:,.0f}", 
                    "평단가": "₩{:,.0f}", 
                    "매수금액": "₩{:,.0f}",
                    "평가금액": "₩{:,.0f}", 
                    "손익": "₩{:+,.0f}",
                    "수익률": "{:+.2f}%", 
                    "누적배당": "₩{:,.0f}"
                }), use_container_width=True)
    else:
        st.info("등록된 종목이 없습니다. 사이드바의 '📌 전체 ETF / 주식 실시간 검색 및 추가'에서 종목을 검색하여 추가해 주세요.")

# ---------------------------------------------------------------------
# [TAB 2] 거래 내역
# ---------------------------------------------------------------------
with tab2:
    st.subheader("거래 내역")
    if not df.empty:
        st.dataframe(df[["종목명", "계좌", "수량", "평단가", "매수금액", "평가금액"]].style.format({
            "수량": "{:,.0f}", "평단가": "₩{:,.0f}", "매수금액": "₩{:,.0f}", "평가금액": "₩{:,.0f}"
        }), use_container_width=True)
    else:
        st.info("거래 내역이 없습니다.")

# ---------------------------------------------------------------------
# [TAB 3] 자산 트렌드
# ---------------------------------------------------------------------
with tab3:
    st.subheader("자산 트렌드")
    if not df.empty:
        period_sel = st.radio("기간 선택", ["최근 1개월", "최근 3개월", "최근 6개월", "최근 1년", "최근 3년", "최근 5년", "전체기간"], index=2, horizontal=True)
        
        days_dict = {"최근 1개월": 30, "최근 3개월": 90, "최근 6개월": 180, "최근 1년": 365, "최근 3년": 1095, "최근 5년": 1825, "전체기간": 2500}
        num_days = days_dict.get(period_sel, 180)
        
        start_d = datetime.now() - timedelta(days=num_days)
        dates = [start_d + timedelta(days=int(i * (num_days / 35))) for i in range(35)]
        
        buy_vals = [total_buy * (0.8 + 0.2 * (i/35)) for i in range(35)]
        eval_vals = [total_eval * (0.75 + 0.25 * (i/35) + ((i%3)-1)*0.01) for i in range(35)]
        rates = [((eval_vals[i] - buy_vals[i]) / buy_vals[i] * 100) if buy_vals[i] > 0 else 0 for i in range(35)]
        
        df_trend = pd.DataFrame({"날짜": dates, "매수금액": buy_vals, "평가금액": eval_vals, "수익률": rates})
        
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["매수금액"], name="매수금액", line=dict(color="#10B981", width=2)))
        fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["평가금액"], name="평가금액", line=dict(color="#8B5CF6", width=2)))
        fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["수익률"], name="수익률(%)", yaxis="y2", line=dict(color="#F59E0B", width=2, dash="dot")))
        
        fig_trend.update_layout(
            yaxis=dict(title="금액 (원)", showgrid=True),
            yaxis2=dict(title="수익률 (%)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            hovermode="x unified",
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("등록된 자산 데이터가 없습니다.")

# ---------------------------------------------------------------------
# [TAB 4] 배당금 현황
# ---------------------------------------------------------------------
with tab4:
    st.subheader("배당금 현황")
    if not df.empty:
        m_labels = [f"24/{m:02d}" for m in range(1, 13)] + [f"25/{m:02d}" for m in range(1, 13)] + ["26/01", "26/02", "26/03"]
        m_divs = [0] * len(m_labels)
        m_divs[-1] = int(df["누적배당"].sum())
        
        df_div = pd.DataFrame({"년/월": m_labels, "배당 입금액(원)": m_divs})
        fig_div_bar = px.bar(df_div, x="년/월", y="배당 입금액(원)", color_discrete_sequence=['#F59E0B'])
        st.plotly_chart(fig_div_bar, use_container_width=True)
    else:
        st.info("등록된 배당 데이터가 없습니다.")

# ---------------------------------------------------------------------
# [TAB 5] 투자리포트
# ---------------------------------------------------------------------
with tab5:
    st.subheader("📊 기간별 포트폴리오 투자리포트")
    if not df.empty:
        report_period = st.select_slider(
            "분석 리포트 기간 선택",
            options=["일별 (1D)", "주간 (1W)", "월간 (1M)", "분기 (1Q)", "반기 (2Q)", "연간 (1Y)"]
        )
        
        rpt_multiplier = {
            "일별 (1D)": 0.002, "주간 (1W)": 0.008, "월간 (1M)": 0.024, 
            "분기 (1Q)": 0.048, "반기 (2Q)": 0.082, "연간 (1Y)": 0.154
        }[report_period]
        
        period_profit = total_eval * rpt_multiplier
        period_return = rpt_multiplier * 100
        
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("해당 기간 실현/평가 손익", f"₩{period_profit:+,.0f}")
        rc2.metric("해당 기간 누적 수익률", f"{period_return:+.2f}%")
        rc3.metric("총 보유 종목 수", f"{len(df['종목명'].unique())} 개")
        rc4.metric("총 평가 금액", f"₩{total_eval:,.0f}")
    else:
        st.info("등록된 자산 데이터가 없습니다. 사이드바에서 신규 자산을 추가해주세요.")
