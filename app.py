import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
import urllib.parse
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
# 2. 강화된 네이버 증권 자동완성 API 및 실시간 시세 수집 엔진
# =====================================================================
def search_stock_autocomplete(query: str):
    """
    네이버 증권 자동완성 API를 연동하여 국내 상장 모든 주식/ETF 검색
    """
    if not query or len(query.strip()) < 1:
        return {}
        
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://ac.finance.naver.com/ac?q={encoded_query}&target=index,stock,etf,fn&r_format=json&r_enc=utf-8&st=111&r_lt=111"
    
    headers = {
        'User-Agent': 'Mozilla/
