import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来·全市场复利雷达", layout="wide")
st.title("🌧️ 等雨来：全市场基本面复利与 PE 分位推演")
st.caption("环境：GitHub Cloud | 数据源：Yahoo Finance 实时点位 | 逻辑：净资产复利 + 10年 PE 分位回归")

# --- 2. 核心指数数据库 (2024/2025 最新基本面锚点) ---
# e_base: 盈利基数 (点位/e_base = 实时PE)
# roe: 目标盈利能力, payout: 平均分红率
# mu/sigma: 过去10年PE的均值与标准差 (用于动态计算百分位)
# pe_20/50/80: 历史PE的关键分位点
INDEX_DB = {
    "宽基指数": {
        "沪深300": {"yf": "000300.SS", "e_base": 312.5, "roe": 0.11, "payout": 0.35, "mu": 12.5, "sigma": 1.8, "p20": 10.8, "p50": 12.5, "p80": 14.5},
        "中证500": {"yf": "000905.SS", "e_base": 180.2, "roe": 0.08, "payout": 0.22, "mu": 27.5, "sigma": 6.5, "p20": 22.0, "p50": 27.5, "p80": 34.0},
        "创业板指": {"yf": "399006.SZ", "e_base": 65.4,  "roe": 0.12, "payout": 0.15, "mu": 42.0, "sigma": 12.0, "p20": 30.0, "p50": 39.0, "p80": 55.0},
        "中证红利": {"yf": "000922.SS", "e_base": 765.4, "roe": 0.12, "payout": 0.55, "mu": 7.5,  "sigma": 1.2, "p20": 6.2,  "p50": 7.5,  "p80": 9.2},
    },
    "港股市场": {
        "恒生指数": {"yf": "^HSI",      "e_base": 1820.5,"roe": 0.10, "payout": 0.45, "mu": 10.5, "sigma": 2.0, "p20": 8.5,  "p50": 10.5, "p80": 12.8},
        "恒生科技": {"yf": "^HSTECH",   "e_base": 165.2, "roe": 0.11, "payout": 0.10, "mu": 28.0, "sigma": 8.5, "p20": 22.0, "p50": 28.0, "p80": 38.0},
    },
    "行业板块": {
        "中证白酒": {"yf": "399997.SZ", "e_base": 485.4, "roe": 0.24, "payout": 0.50, "mu": 32.0, "sigma": 9.0, "p20": 23.5, "p50": 32.0, "p80": 45.0},
        "中证医疗": {"yf": "399989.SZ", "e_base": 282.1, "roe": 0.13, "payout": 0.20, "mu": 38.0, "sigma": 12.5, "p20": 27.0, "p50": 38.0, "p80": 52.0},
        "中国互联网":{"yf": "3067.HK",    "e_base": 2.45,  "roe": 0.12, "payout": 0.15, "mu": 22.0, "sigma": 7.0, "p20": 17.5, "p50": 22.0, "p80": 32.0},
    }
}

# --- 3. 核心计算函数 ---
def calculate_roi(current_pe, target_pe, roe, payout, n):
    # 内生增长率 g = ROE * (1 - 分红率)
    g = roe * (1 - payout)
    # 终值 = (1 + g)^n * (目标PE / 当前PE)
    # 注意：我们这里假设当前ROE处于合理水平，暂不计ROE修复带来的额外双击，以保持稳健
    future_value = ((1 + g) ** n) * (target_pe / current_pe)
    # 扣除本金后的纯收益率
    return (future_value - 1) * 100

# --- 4. 侧边栏与交互 ---
st.sidebar.header("🎯 模拟参数")
n_years = st.sidebar.slider("推演未来年限 (n)", 1, 10, 3)

# --- 5. 执行抓取与展示 ---
all_results = []
status_text = st.empty()

for cat, indices in INDEX_DB.items():
    status_text.text(f"正在实时获取 {cat} 数据...")
    for name, cfg in indices.items():
        try:
            ticker = yf.Ticker(cfg['yf'])
            price = ticker.history(period="1d")['Close'].iloc[-1]
            
            # 实时 PE-TTM
            live_pe = price / cfg['e_base']
            # 计算 10 年分位
            percentile = norm.cdf(live_pe, cfg['mu'], cfg['sigma']) * 100
            
            # 推演不同分位下的纯收益率
            roi_20 = calculate_roi(live_pe, cfg['p20'], cfg['roe'], cfg['payout'], n_years)
            roi_50 = calculate_roi(live_pe, cfg['p50'], cfg['roe'], cfg['payout'], n_years)
            roi_80 = calculate_roi(live_pe, cfg['p80'], cfg['roe'], cfg['payout'], n_years)
            
            all_results.append({
                "指数": name,
                "实时 PE": round(live_pe, 2),
                "10年分位": f"{percentile:.1f}%",
                "状态": "☀️ 过热" if percentile > 80 else ("🌧️ 等雨" if percentile < 20 else "⛅ 观望"),
                "20%分位(悲观)": f"{roi_20:.1f}%",
                "50%分位(合理)": f"{roi_50:.1f}%",
                "80%分位(乐观)": f"{roi_80:.1f}%",
            })
        except:
            continue

status_text.empty()

if all_results:
    df = pd.DataFrame(all_results)
    st.subheader(f"📊 {n_years}年后预期纯收益率推演 (扣除本金)")
    
    # 样式美化
    st.table(df.style.applymap(lambda x: 'color: red' if '-' in str(x) else 'color: green', 
                               subset=['20%分位(悲观)', '50%分位(合理)', '80%分位(乐观)']))
    
    st.markdown("""
    ---
    ### 📖 结果解读
    1. **实时 PE 真实性**：通过 Yahoo Finance 实时价格反推。当 **中证500** 价格上涨，实时 PE 会自动升高。
    2. **不同水位收益率**：
       - **20% 分位 (悲观)**：如果未来市场依然低迷，仅修复到历史极差水平。
       - **50% 分位 (合理)**：回归到 10 年中轴，这是等雨来策略的**核心盈利点**。
       - **80% 分位 (乐观)**：产生戴维斯双击，享受牛市过热红利。
    3. **为何收益率不同？**
       - **白酒/互联网**：ROE 目标高，即便 PE 不涨，靠净资产内生增长（g）也能撑起较高的复利。
       - **红利指数**：分红率高，净资产增长慢，收益更依赖于股息和低 PE 的回归。
    """)
else:
    st.error("数据调取失败。请确认 GitHub 是否能访问 Yahoo Finance 接口。")
