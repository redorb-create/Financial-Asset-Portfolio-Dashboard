import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

# =====================================================================
# 1. 페이지 설정 및 PENSION TREE 스타일 CSS
# =====================================================================
st.set_page_config(
    page_title="PENSION TREE - 자산 & 연금 관리",
    page_icon="🌱",
    layout="wide"
)

# PENSION TREE 전용 CSS 디자인
st.markdown("""
<style>
    .brand-header {
        font-size: 24px;
        font-weight: 800;
        color: #2ECC71;
        letter-spacing: 1px;
    }
    .summary-banner {
        background-color: #F8F9FA;
        border: 1px solid #E9ECEF;
        border-radius: 8px;
        padding: 12px 24px;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 20px;
        font-size: 15px;
        font-weight: 600;
        margin-bottom: 25px;
    }
    .summary-val { color: #212529; font-weight: 700; }
    .summary-eval { color: #2B6CB0; font-weight: 700; }
    .summary-profit { color: #E53E3E; font-weight: 700; }

    .stock-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .stock-title { font-size: 16px; font-weight: 700; color: #1A202C; }
    .stock-price { font-size: 14px; font-weight: 700; color: #E53E3E; text-align: right; }
    .card-label { font-size: 12px; color: #718096; }
    .card-num { font-size: 13px; font-weight: 600; color: #2D3748; }
    .card-profit-plus { font-size: 13px; font-weight: 700; color: #E53E3E; }
    .card-profit-minus { font-size: 13px; font-weight: 700; color: #3182CE; }
</style>
""", unsafe_allow_html=True)

# 비밀번호 인증
DASHBOARD_PASSWORD = st.secrets.get("DASHBOARD_PASSWORD", "1234")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h2 style='text-align: center; color: #2ECC71;'>🌱 PENSION TREE</h2>", unsafe_allow_html=True)
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
# 2. 초고속 네비게이션 & yfinance 실시간 시세 수집 엔진
# =====================================================================
@st.cache_data(ttl=30)  # 30초 간격 캐싱
def fetch_realtime_market_data(ticker_list: tuple):
    """
    한국 주식/ETF는 네이버 금융 크롤링으로 실시간 100% 정밀 조회
    미국 주식/ETF 및 환율은 yfinance 조회
    """
    price_data = {}
    
    # 1. USD/KRW 환율 수집
    try:
        usd_krw_ticker = yf.Ticker("KRW=X")
        usd_krw = float(usd_krw_ticker.fast_info.get('lastPrice', 1350.0))
    except Exception:
        usd_krw = 1350.0

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for symbol in set(ticker_list):
        if not symbol or symbol == "-":
            continue
            
        curr_price = 0.0
        is_usd = not symbol.endswith((".KS", ".KQ"))
        
        # [A] 한국 주식/ETF: 네이버 금융 실시간 조회 (지연 없음)
        if symbol.endswith((".KS", ".KQ")):
            code = re.sub(r'[^0-9]', '', symbol)  # 종목코드 6자리 추출 (예: 178260)
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            try:
                res = requests.get(url, headers=headers, timeout=3)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    no_today = soup.find('p', class_='no_today')
                    if no_today:
                        price_str = no_today.find('span', class_='blind').text.replace(',', '')
                        curr_price = float(price_str)
            except Exception:
                curr_price = 0.0

        # [B] 미국 주식/ETF 또는 네이버 예외 시: yfinance 조회
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
# 3. 계좌 및 보유 종목 세션 DB 초기화
# =====================================================================
if "account_list" not in st.session_state:
    st.session_state.account_list = ["미래에셋 DC", "미래에셋 연금저축", "미래에셋 IRP", "신한은행 DC", "KB국민은행 IRP"]

if "portfolio_db" not in st.session_state:
    st.session_state.portfolio_db = pd.DataFrame([
        {"종목명": "PLUS 고배당주", "티커": "161510.KS", "계좌": "미래에셋 DC", "수량": 5702, "평단가": 20198, "현재가": 0.0, "매수금액": 115167780, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 2202810},
        {"종목명": "TIGER 미국배당다우존스", "티커": "458730.KS", "계좌": "미래에셋 연금저축", "수량": 2538, "평단가": 11406, "현재가": 0.0, "매수금액": 28947721, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 1782087},
        {"종목명": "TIGER 미국배당다우존스", "티커": "458730.KS", "계좌": "미래에셋 IRP", "수량": 2919, "평단가": 10849, "현재가": 0.0, "매수금액": 31668460, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 2050193},
        {"종목명": "KODEX TDF2050액티브", "티커": "431040.KS", "계좌": "미래에셋 DC", "수량": 6484, "평단가": 15295, "현재가": 0.0, "매수금액": 99174321, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 969224},
        {"종목명": "KODEX 미국배당커버드콜액티브", "티커": "441640.KS", "계좌": "미래에셋 DC", "수량": 5454, "평단가": 12824, "현재가": 0.0, "매수금액": 69940905, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 708466},
        {"종목명": "KODEX 미국나스닥100", "티커": "178260.KS", "계좌": "미래에셋 DC", "수량": 2325, "평단가": 24697, "현재가": 0.0, "매수금액": 57420775, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 157080},
        {"종목명": "RISE 머니마켓액티브", "티커": "459590.KS", "계좌": "미래에셋 DC", "수량": 1020, "평단가": 54506, "현재가": 0.0, "매수금액": 55596261, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 1523115},
        {"종목명": "SOL 미국배당다우존스", "티커": "446720.KS", "계좌": "신한은행 DC", "수량": 2412, "평단가": 9095, "현재가": 0.0, "매수금액": 21937917, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 2134887},
        {"종목명": "TIGER KRX금현물", "티커": "411060.KS", "계좌": "미래에셋 DC", "수량": 1322, "평단가": 12967, "현재가": 0.0, "매수금액": 17142565, "평가금액": 0.0, "손익": 0.0, "수익률": 0.0, "누적배당": 1378}
    ])

# 네이버 금융 실시간 현재가 즉시 동기화
if not st.session_state.portfolio_db.empty:
    tickers = tuple(st.session_state.portfolio_db["티커"].unique())
    realtime_prices, current_usd_krw = fetch_realtime_market_data(tickers)
    
    for idx, row in st.session_state.portfolio_db.iterrows():
        symbol = row["티커"]
        if symbol in realtime_prices and realtime_prices[symbol]["현재가"] > 0:
            m_data = realtime_prices[symbol]
            curr_p = m_data["현재가"]
            if m_data["통화"] == "USD":
                curr_p *= current_usd_krw
            
            st.session_state.portfolio_db.at[idx, "현재가"] = curr_p
            st.session_state.portfolio_db.at[idx, "평가금액"] = row["수량"] * curr_p
            st.session_state.portfolio_db.at[idx, "손익"] = (row["수량"] * curr_p) - row["매수금액"]
            if row["매수금액"] > 0:
                st.session_state.portfolio_db.at[idx, "수익률"] = round(
                    (st.session_state.portfolio_db.at[idx, "손익"] / row["매수금액"]) * 100, 2
                )

df = st.session_state.portfolio_db

# 상단 배너용 통합 합계 계산
total_buy = df["매수금액"].sum() if not df.empty else 0
total_eval = df["평가금액"].sum() if not df.empty else 0
total_profit = total_eval - total_buy
total_rate = (total_profit / total_buy * 100) if total_buy > 0 else 0.0

# =====================================================================
# 4. 사이드바 - 계좌 & 종목 추가/삭제
# =====================================================================
with st.sidebar:
    st.header("⚙️ PENSION TREE 관리")
    
    if st.button("🔄 실시간 시세/환율 즉시 갱신", use_container_width=True):
        st.cache_data.clear()
        st.success("실시간 시세가 갱신되었습니다!")
        st.rerun()
        
    st.markdown("---")
    
    # 1) 계좌 관리
    with st.expander("🏦 계좌 추가 / 삭제"):
        st.subheader("계좌 추가")
        new_acc_name = st.text_input("새 계좌명 (예: 토스증권 주식)")
        if st.button("계좌 등록", use_container_width=True):
            if new_acc_name and new_acc_name not in st.session_state.account_list:
                st.session_state.account_list.append(new_acc_name)
                st.success(f"'{new_acc_name}' 계좌 추가 완료!")
                st.rerun()
                
        st.markdown("---")
        st.subheader("계좌 삭제")
        del_acc_target = st.selectbox("삭제할 계좌 선택", options=st.session_state.account_list)
        if st.button("선택 계좌 삭제", use_container_width=True):
            st.session_state.account_list.remove(del_acc_target)
            st.session_state.portfolio_db = st.session_state.portfolio_db[
                st.session_state.portfolio_db["계좌"] != del_acc_target
            ].reset_index(drop=True)
            st.success(f"'{del_acc_target}' 계좌 삭제 완료!")
            st.rerun()

    # 2) 종목 관리
    with st.expander("📌 종목 보유내역 추가"):
        with st.form("add_item_form"):
            in_acc = st.selectbox("계좌 선택", options=st.session_state.account_list)
            in_name = st.text_input("종목명", value="KODEX 200")
            in_ticker = st.text_input("티커/코드 (미국 AAPL, 한국 069500.KS)", value="069500.KS")
            in_qty = st.number_input("수량", min_value=1, value=100)
            in_avg = st.number_input("평단가(원)", min_value=0, value=35000)
            in_div = st.number_input("누적 배당금(원)", min_value=0, value=0)
            
            if st.form_submit_button("보유 종목 저장", use_container_width=True):
                buy_amt = in_qty * in_avg
                
                new_row = pd.DataFrame([{
                    "종목명": in_name, "티커": in_ticker.strip(), "계좌": in_acc,
                    "수량": in_qty, "평단가": in_avg, "현재가": 0.0,
                    "매수금액": buy_amt, "평가금액": buy_amt,
                    "손익": 0.0, "수익률": 0.0, "누적배당": in_div
                }])
                
                st.session_state.portfolio_db = pd.concat([st.session_state.portfolio_db, new_row], ignore_index=True)
                st.cache_data.clear()
                st.success(f"'{in_name}' 종목 추가 완료!")
                st.rerun()

    with st.expander("🗑️ 보유 종목 삭제"):
        if not st.session_state.portfolio_db.empty:
            temp_df = st.session_state.portfolio_db.copy()
            temp_df["item_label"] = temp_df["종목명"] + " (" + temp_df["계좌"] + ")"
            del_item_target = st.selectbox("삭제할 항목 선택", options=temp_df["item_label"].unique())
            
            if st.button("보유 종목 삭제", use_container_width=True):
                selected_idx = temp_df[temp_df["item_label"] == del_item_target].index
                st.session_state.portfolio_db = st.session_state.portfolio_db.drop(selected_idx).reset_index(drop=True)
                st.success("선택한 종목 삭제 완료!")
                st.rerun()
        else:
            st.write("삭제할 보유 종목이 없습니다.")

# =====================================================================
# 5. 메인 대시보드 화면 (PENSION TREE 4개 메인 탭)
# =====================================================================
col_brand, col_banner = st.columns([1, 3])

with col_brand:
    st.markdown('<div class="brand-header">🌱 PENSION TREE</div>', unsafe_allow_html=True)

with col_banner:
    st.markdown(f'''
    <div class="summary-banner">
        <div>매수 <span class="summary-val">{total_buy:,.0f}</span></div>
        <div>평가 <span class="summary-eval">{total_eval:,.0f}</span></div>
        <div>수익 <span class="summary-profit">{total_profit:+,.0f} ({total_rate:+.2f}%)</span></div>
        <div style="color:#718096;">↗ 0 (0.00%)</div>
    </div>
    ''', unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 종목별 & 계좌별 현황", 
    "📑 거래 내역", 
    "📈 자산 트렌드", 
    "💸 배당금 현황"
])

# ---------------------------------------------------------------------
# [TAB 1] 종목별 현황 (Grid Card) & 계좌별 보유현황
# ---------------------------------------------------------------------
with tab1:
    st.subheader("종목별 현황")
    
    if not df.empty:
        grouped_stock = df.groupby("종목명").agg({
            "현재가": "first",
            "수량": "sum",
            "매수금액": "sum",
            "평가금액": "sum",
            "손익": "sum",
            "누적배당": "sum"
        }).reset_index()
        grouped_stock["수익률"] = (grouped_stock["손익"] / grouped_stock["매수금액"] * 100).round(2)
        
        # 4열 그리드 카드 배치
        cols = st.columns(4)
        for idx, row in grouped_stock.iterrows():
            col_idx = idx % 4
            profit_class = "card-profit-plus" if row["손익"] >= 0 else "card-profit-minus"
            with cols[col_idx]:
                st.markdown(f'''
                <div class="stock-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="stock-title">{row['종목명']}</div>
                        <div class="stock-price">{row['현재가']:,.0f}</div>
                    </div>
                    <hr style="margin:8px 0; border:none; border-top:1px solid #EDF2F7;">
                    <div style="display:flex; justify-content:space-between;">
                        <div><span class="card-label">보유수량</span><br><span class="card-num">{row['수량']:,.0f}주</span></div>
                        <div style="text-align:right;"><span class="card-label">평단가</span><br><span class="card-num">{(row['매수금액']/row['수량']):,.0f}</span></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:6px;">
                        <div><span class="card-label">총 매수금</span><br><span class="card-num">{row['매수금액']:,.0f}</span></div>
                        <div style="text-align:right;"><span class="card-label">총 평가금</span><br><span class="card-num">{row['평가금액']:,.0f}</span></div>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-top:6px;">
                        <div><span class="card-label">전체 수익금</span><br><span class="{profit_class}">{row['손익']:+,.0f}</span></div>
                        <div style="text-align:right;"><span class="card-label">전체 수익률</span><br><span class="{profit_class}">{row['수익률']:+.2f}%</span></div>
                    </div>
                    <div style="margin-top:6px; text-align:right; font-size:12px; color:#2ECC71; font-weight:600;">
                        누적 배당금: ₩{row['누적배당']:,.0f}
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
        st.info("등록된 종목 및 계좌 보유 데이터가 없습니다. 사이드바에서 추가해주세요.")

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
# [TAB 3] 자산 트렌드 (듀얼 Y축)
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
    fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["매수금액"], name="매수금액", line=dict(color="#2ECC71", width=2)))
    fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["평가금액"], name="평가금액", line=dict(color="#8E44AD", width=2)))
    fig_trend.add_trace(go.Scatter(x=df_trend["날짜"], y=df_trend["수익률"], name="수익률(%)", yaxis="y2", line=dict(color="#F1C40F", width=2, dash="dot")))
    
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
    
    fig_div_bar = px.bar(x=m_labels, y=m_divs, labels={'x': '년/월', 'y': '배당 입금액(원)'}, color_discrete_sequence=['#F1C40F'])
    st.plotly_chart(fig_div_bar, use_container_width=True)
