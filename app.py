import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
from datetime import datetime, timedelta

# =====================================================================
# 1. 페이지 설정 및 다크모드 대응 반응형 CSS
# =====================================================================
st.set_page_config(
    page_title="개인 금융자산 포트폴리오 대시보드",
    page_icon="📈",
    layout="wide"
)

# 다크 모드 및 라이트 모드 가시성 보장 & 미니 상단 버튼 CSS
st.markdown("""
<style>
    /* 헤더 타이틀 배너 (이미지 제거 및 간결화) */
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

    /* 상단 자산 요약 요약바 */
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

    /* 종목 카드 컨테이너 */
    .stock-card {
        background-color: var(--background-secondary-color, #FFFFFF);
        border: 1px solid var(--border-color, #E2E8F0);
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 8px;
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

    /* [요구사항 1] 상단 우측 정렬 1/4 미니 컨트롤 버튼 전용 스타일 */
    .mini-btn-group {
        display: flex;
        justify-content: flex-end;
        gap: 2px;
        margin-bottom: 4px;
    }
    .mini-btn-group .stButton > button {
        border-radius: 3px !important;
        border: 1px solid var(--border-color, #CBD5E1) !important;
        background-color: transparent !important;
        color: var(--text-color-secondary, #64748B) !important;
        padding: 0px 4px !important;
        font-size: 9px !important;       /* 1/4 크기로 축소 */
        line-height: 12px !important;
        height: 18px !important;         /* 버튼 높이 슬림화 */
        min-height: 18px !important;
        width: 22px !important;          /* 소형 크기 지정 */
    }
    .mini-btn-group .stButton > button:hover {
        background-color: rgba(148, 163, 184, 0.2) !important;
        border-color: #94A3B8 !important;
        color: var(--text-color, #0F172A) !important;
    }
</style>
""", unsafe_allow_html=True)

# 비밀번호 설정
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
# 2. 네이버 증권 모바일 API 기반 실시간 시세 수집 모듈
# =====================================================================
@st.cache_data(ttl=30)
def fetch_realtime_market_data(ticker_list: tuple):
    price_data = {}
    try:
        usd_krw_ticker = yf.Ticker("KRW=X")
        usd_krw = float(usd_krw_ticker.fast_info.get('lastPrice', 1350.0))
    except Exception:
        usd_krw = 1350.0

    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
    }

    for symbol in set(ticker_list):
        if not symbol or symbol == "-":
            continue
            
        curr_price = 0.0
        is_usd = not symbol.endswith((".KS", ".KQ"))
        
        # 한국 주식/ETF: 네이버 모바일 API
        if symbol.endswith((".KS", ".KQ")):
            code = re.sub(r'[^0-9]', '', symbol)
            url = f"https://m.stock.naver.com/api/stock/{code}/basic"
            try:
                res = requests.get(url, headers=headers, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    price_raw = data.get('nowVal', '0').replace(',', '')
                    curr_price = float(price_raw)
            except Exception:
                curr_price = 0.0

        # 미국 주식 및 백업: yfinance
        if curr_price == 0.0:
            try:
                t = yf.Ticker(symbol)
                curr_price = t.fast_info.get('lastPrice', 0.0)
                if curr_price == 0.0:
                    hist = t.history(period="1d")
                    if not hist.empty:
                        curr_price = hist['Close'].iloc[-1]
            except Exception:
                curr_price = 0.0
                
        price_data[symbol] = {
            "현재가": float(curr_price),
            "통화": "USD" if is_usd else "KRW"
        }
        
    return price_data, usd_krw

# =====================================================================
# 3. 데이터베이스 및 세션 상태 초기화
# =====================================================================
if "account_list" not in st.session_state:
    st.session_state.account_list = ["미래에셋 DC", "미래에셋 연금저축", "미래에셋 IRP", "신한은행 DC", "KB국민은행 IRP"]

if "portfolio_db" not in st.session_state:
    st.session_state.portfolio_db = pd.DataFrame([
        {"종목명": "PLUS 고배당주", "티커": "161510.KS", "계좌": "미래에셋 DC", "수량": 5702, "평단가": 20198, "현재가": 26175, "매수금액": 115167780, "평가금액": 149249850, "손익": 34082070, "수익률": 29.59, "누적배당": 2202810},
        {"종목명": "TIGER 미국배당다우존스", "티커": "458730.KS", "계좌": "미래에셋 연금저축", "수량": 2538, "평단가": 11406, "현재가": 14425, "매수금액": 28947721, "평가금액": 36611650, "손익": 7663929, "수익률": 26.47, "누적배당": 1782087},
        {"종목명": "TIGER 미국배당다우존스", "티커": "458730.KS", "계좌": "미래에셋 IRP", "수량": 2919, "평단가": 10849, "현재가": 14425, "매수금액": 31668460, "평가금액": 42106575, "손익": 10438115, "수익률": 32.96, "누적배당": 2050193},
        {"종목명": "KODEX TDF2050액티브", "티커": "431040.KS", "계좌": "미래에셋 DC", "수량": 6484, "평단가": 15295, "현재가": 16455, "매수금액": 99174321, "평가금액": 106694220, "손익": 7519899, "수익률": 7.58, "누적배당": 969224},
        {"종목명": "KODEX 미국배당커버드콜액티브", "티커": "441640.KS", "계좌": "미래에셋 DC", "수량": 5454, "평단가": 12824, "현재가": 12785, "매수금액": 69940905, "평가금액": 69729390, "손익": -211515, "수익률": -0.30, "누적배당": 708466},
        {"종목명": "KODEX 미국나스닥100", "티커": "178260.KS", "계좌": "미래에셋 DC", "수량": 2325, "평단가": 24697, "현재가": 26410, "매수금액": 57420775, "평가금액": 61403250, "손익": 3982475, "수익률": 6.94, "누적배당": 157080},
        {"종목명": "RISE 머니마켓액티브", "티커": "459590.KS", "계좌": "미래에셋 DC", "수량": 1020, "평단가": 54506, "현재가": 54655, "매수금액": 55596261, "평가금액": 55748100, "손익": 151839, "수익률": 0.27, "누적배당": 1523115},
        {"종목명": "SOL 미국배당다우존스", "티커": "446720.KS", "계좌": "신한은행 DC", "수량": 2412, "평단가": 9095, "현재가": 13235, "매수금액": 21937917, "평가금액": 31922820, "손익": 9984903, "수익률": 45.51, "누적배당": 2134887},
        {"종목명": "TIGER KRX금현물", "티커": "411060.KS", "계좌": "미래에셋 DC", "수량": 1322, "평단가": 12967, "현재가": 16260, "매수금액": 17142565, "평가금액": 21495720, "손익": 4353155, "수익률": 25.39, "누적배당": 1378}
    ])

if "editing_stock" not in st.session_state:
    st.session_state.editing_stock = None

# 실시간 주가 반영
if not st.session_state.portfolio_db.empty:
    tickers = tuple(st.session_state.portfolio_db["티커"].unique())
    realtime_prices, current_usd_krw = fetch_realtime_market_data(tickers)
    
    for idx, row in st.session_state.portfolio_db.iterrows():
        symbol = row["티커"]
        curr_p = 0.0
        
        if symbol in realtime_prices:
            curr_p = realtime_prices[symbol]["현재가"]
            if realtime_prices[symbol]["통화"] == "USD":
                curr_p *= current_usd_krw

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
# 4. 사이드바 - 관리 메뉴
# =====================================================================
with st.sidebar:
    st.header("⚙️ 포트폴리오 설정")
    
    if st.button("🔄 실시간 시세 즉시 갱신", use_container_width=True):
        st.cache_data.clear()
        st.success("실시간 시세가 반영되었습니다!")
        st.rerun()
        
    st.markdown("---")
    
    with st.expander("🏦 계좌 관리 (추가/삭제)"):
        st.subheader("계좌 추가")
        new_acc_name = st.text_input("새 계좌명")
        if st.button("계좌 등록", use_container_width=True):
            if new_acc_name and new_acc_name not in st.session_state.account_list:
                st.session_state.account_list.append(new_acc_name)
                st.success(f"'{new_acc_name}' 추가 완료!")
                st.rerun()
                
        st.markdown("---")
        st.subheader("계좌 삭제")
        del_acc_target = st.selectbox("삭제할 계좌", options=st.session_state.account_list)
        if st.button("선택 계좌 삭제", use_container_width=True):
            st.session_state.account_list.remove(del_acc_target)
            st.session_state.portfolio_db = st.session_state.portfolio_db[
                st.session_state.portfolio_db["계좌"] != del_acc_target
            ].reset_index(drop=True)
            st.success(f"'{del_acc_target}' 삭제 완료!")
            st.rerun()

    with st.expander("📌 종목 보유내역 추가"):
        with st.form("add_item_form"):
            in_acc = st.selectbox("계좌 선택", options=st.session_state.account_list)
            in_name = st.text_input("종목명", value="KODEX 200")
            in_ticker = st.text_input("티커/코드 (예: 069500.KS)", value="069500.KS")
            in_qty = st.number_input("수량", min_value=1, value=100)
            in_avg = st.number_input("평단가(원)", min_value=0, value=35000)
            in_div = st.number_input("누적 배당금(원)", min_value=0, value=0)
            
            if st.form_submit_button("보유 종목 저장", use_container_width=True):
                buy_amt = in_qty * in_avg
                new_row = pd.DataFrame([{
                    "종목명": in_name, "티커": in_ticker.strip(), "계좌": in_acc,
                    "수량": in_qty, "평단가": in_avg, "현재가": in_avg,
                    "매수금액": buy_amt, "평가금액": buy_amt,
                    "손익": 0.0, "수익률": 0.0, "누적배당": in_div
                }])
                st.session_state.portfolio_db = pd.concat([st.session_state.portfolio_db, new_row], ignore_index=True)
                st.cache_data.clear()
                st.success(f"'{in_name}' 추가 완료!")
                st.rerun()

# =====================================================================
# 5. [요구사항 2] 헤더 타이틀 (이미지 제거)
# =====================================================================
st.markdown('''
<div class="dashboard-header">
    <div>
        <h1 class="dashboard-title">📈 개인 금융자산 포트폴리오 대시보드</h1>
        <p class="dashboard-subtitle">실시간 시세 연동 및 계좌별 자산/연금/배당 관리 통합 시스템</p>
    </div>
</div>
''', unsafe_allow_html=True)

# 상단 자산 요약 배너
profit_style_class = "summary-profit-plus" if total_profit >= 0 else "summary-profit-minus"
st.markdown(f'''
<div class="summary-banner">
    <div>총 매수 <span class="summary-val">{total_buy:,.0f} 원</span></div>
    <div>총 평가 <span class="summary-eval">{total_eval:,.0f} 원</span></div>
    <div>총 손익 <span class="{profit_style_class}">{total_profit:+,.0f} 원 ({total_rate:+.2f}%)</span></div>
</div>
''', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 종목별 & 계좌별 현황", 
    "📑 거래 내역", 
    "📈 자산 트렌드", 
    "💸 배당금 현황"
])

# ---------------------------------------------------------------------
# [TAB 1] 종목별 현황 (요구사항 1: 상단 우측 정렬 1/4 크기 미니 모노톤 버튼)
# ---------------------------------------------------------------------
with tab1:
    st.subheader("종목별 현황")
    
    if not df.empty:
        unique_stocks = list(df["종목명"].unique())
        
        # 종목 수정 폼
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
                    if st.form_submit_button("저장", use_container_width=True):
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
                    if st.form_submit_button("취소", use_container_width=True):
                        st.session_state.editing_stock = None
                        st.rerun()
            st.markdown("---")

        # 4열 카드 배치
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
                # [요구사항 1] 상단 우측 정렬 1/4 크기 미니 버튼 그룹
                st.markdown('<div class="mini-btn-group">', unsafe_allow_html=True)
                mb1, mb2, mb3, mb4 = st.columns([1, 1, 1, 1])
                with mb1:
                    if st.button("⬆", key=f"up_{name}", help="위로 이동"):
                        if idx > 0:
                            prev_name = unique_stocks[idx-1]
                            idx_a = df[df["종목명"] == name].index
                            idx_b = df[df["종목명"] == prev_name].index
                            new_df = pd.concat([df.loc[idx_a], df.loc[idx_b], df.drop(idx_a.union(idx_b))]).reset_index(drop=True)
                            st.session_state.portfolio_db = new_df
                            st.rerun()
                with mb2:
                    if st.button("⬇", key=f"down_{name}", help="아래로 이동"):
                        if idx < len(unique_stocks) - 1:
                            next_name = unique_stocks[idx+1]
                            idx_a = df[df["종목명"] == name].index
                            idx_b = df[df["종목명"] == next_name].index
                            new_df = pd.concat([df.drop(idx_a.union(idx_b)), df.loc[idx_b], df.loc[idx_a]]).reset_index(drop=True)
                            st.session_state.portfolio_db = new_df
                            st.rerun()
                with mb3:
                    if st.button("✏", key=f"edit_{name}", help="수정"):
                        st.session_state.editing_stock = name
                        st.rerun()
                with mb4:
                    if st.button("✕", key=f"del_{name}", help="삭제"):
                        st.session_state.portfolio_db = st.session_state.portfolio_db[
                            st.session_state.portfolio_db["종목명"] != name
                        ].reset_index(drop=True)
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

                # 종목 카드 내용
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

# ---------------------------------------------------------------------
# [TAB 2] 거래 내역
# ---------------------------------------------------------------------
with tab2:
    st.subheader("거래 내역")
    tx_records = [
        {"거래일": "2026-03-10", "계좌": "미래에셋 연금저축", "종목": "KODEX 미국배당커버드콜액티브", "구분": "매수", "수량": 233, "단가": 12845, "거래금액": 2992885},
        {"거래일": "2026-03-09", "계좌": "미래에셋 DC", "종목": "KODEX 미국배당커버드콜액티브", "구분": "매수", "수량": 781, "단가": 12815, "거래금액": 10008515},
        {"거래일": "2026-03-09", "계좌": "미래에셋 DC", "종목": "PLUS 고배당주", "구분": "매수", "수량": 407, "단가": 24540, "거래금액": 9987780}
    ]
    st.dataframe(pd.DataFrame(tx_records).style.format({
        "수량": "{:,.0f}", "단가": "₩{:,.0f}", "거래금액": "₩{:,.0f}"
    }), use_container_width=True)

# ---------------------------------------------------------------------
# [TAB 3] 자산 트렌드
# ---------------------------------------------------------------------
with tab3:
    st.subheader("자산 트렌드")
    period_sel = st.radio("기간 선택", ["최근 1개월", "최근 3개월", "최근 6개월", "최근 1년", "최근 3년", "최근 5년", "전체기간"], index=2, horizontal=True)
    
    dates = [datetime(2025, 9, 23) + timedelta(days=i*5) for i in range(35)]
    buy_vals = [430000000 + i*3000000 for i in range(35)]
    eval_vals = [440000000 + i*5000000 + (i%3)*4000000 for i in range(35)]
    rates = [(eval_vals[i] - buy_vals[i]) / buy_vals[i] * 100 for i in range(35)]
    
    df_trend = pd.DataFrame({"날짜": dates, "매수금액": buy_vals, "평가금액": eval_vals, "수익률": rates})
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["매수금액"], name="매수금액", line=dict(color="#10B981", width=2)))
    fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["평가금액"], name="평가금액", line=dict(color="#8B5CF6", width=2)))
    fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["수익률"], name="수익률(%)", yaxis="y2", line=dict(color="#F59E0B", width=2, dash="dot")))
    
    fig_trend.update_layout(
        yaxis=dict(title="금액 (원)"),
        yaxis2=dict(title="수익률 (%)", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        hovermode="x unified"
    )
    st.plotly_chart(fig_trend, use_container_width=True)

# ---------------------------------------------------------------------
# [TAB 4] 배당금 현황
# ---------------------------------------------------------------------
with tab4:
    st.subheader("배당금 현황")
    m_labels = [f"24/{m:02d}" for m in range(1, 13)] + [f"25/{m:02d}" for m in range(1, 13)] + ["26/01", "26/02", "26/03"]
    m_divs = [200000, 250000, 300000, 280000, 450000, 420000, 430000, 410000, 480000, 500000, 520000, 550000,
              480000, 510000, 530000, 720000, 680000, 650000, 660000, 670000, 850000, 2400000, 1050000, 1800000, 852150]
    
    fig_div_bar = px.bar(x=m_labels, y=m_divs, labels={'x': '년/월', 'y': '배당 입금액(원)'}, color_discrete_sequence=['#F59E0B'])
    st.plotly_chart(fig_div_bar, use_container_width=True)
