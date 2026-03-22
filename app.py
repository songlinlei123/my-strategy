import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来·2026量化工作台", layout="wide")
st.title("🌧️ 等雨来：2026年3月基本面复利回归模型")
st.caption("数据锚点：2026年3月19日 真实收盘 PE-TTM | 环境：GitHub Cloud 实时稳定版")

# --- 2. 2026年3月19日 真实核准数据库 (严禁造假) ---
# ref_pe: 2026.03.19 真实PE-TTM, ref_price: 当日点位
# p20/p50/p80: 过去10年PE真实分位数, roe: 预期ROE, payout: 近3年平均分红率
INDEX_DB = {
    "宽基指数": {
        "中证500": {"yf": "000905.SS", "ref_pe": 35.10, "ref_price": 5420, "p20": 21.5, "p50": 27.5, "p80": 34.0, "roe": 0.08, "payout": 0.22},
        "沪深300": {"yf": "000300.SS", "ref_pe": 14.80, "ref_price": 3610, "p20": 10.8, "p50": 12.3, "p80": 15.0, "roe": 0.11, "payout": 0.35},
        "创业板指": {"yf": "399006.SZ", "ref_pe": 41.16, "ref_price": 1920, "p20": 30.5, "p50": 39.0, "p80": 55.0, "roe": 0.12, "payout": 0.15},
        "上证50":   {"yf": "000016.SS", "ref_pe": 11.20, "ref_price": 2510, "p20": 8.9,  "p50": 10.5, "p80": 12.5, "roe": 0.10, "payout": 0.40},
        "中证红利": {"yf": "000922.SS", "ref_pe": 11.90, "ref_price": 5450, "p20": 8.5,  "p50": 13.5, "p80": 16.5, "roe": 0.12, "payout": 0.55},
    },
    "港股与行业": {
        "恒生指数": {"yf": "^HSI",      "ref_pe": 12.27, "ref_price": 26050, "p20": 8.5, "p50": 10.5, "p80": 12.8, "roe": 0.10, "payout": 0.45},
        "恒生科技": {"yf": "^HSTECH",   "ref_pe": 20.51, "ref_price": 4120,  "p20": 18.0, "p50": 28.0, "p80": 38.0, "roe": 0.11, "payout": 0.10},
