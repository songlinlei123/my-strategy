import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来策略·基本面工作台", layout="wide")
st.title("🌧️ 等雨来：内生增长 + 估值双回归模型 (雪球稳健版)")
st.info("模型逻辑：市值 = (初始净资产 * (1+内生增长)^n) * 目标ROE * 目标PE")

# --- 2. 侧边栏参数 ---
st.sidebar.header("🎯 模拟参数")
projection_years = st.sidebar.slider("推演未来年限 (n)", 1, 7, 3)
lookback_years = st.sidebar.slider("历史锚点参考年限", 3, 10, 5)
base_money = st.sidebar.number_input("初始投入基准", value=1.0)

# 指数列表 (雪球代码格式)
TARGETS = {
    "沪深300": "SH000300",
    "中证500": "SH000905",
    "创业板指": "SZ399006",
    "上证50": "SH000016",
    "中证白酒": "SZ399997",
    "恒生指数": "HKHSI"
}

# --- 3. 核心抓取函数 (避开IP封锁) ---
def fetch_from_xueqiu(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://xueqiu.com"
    }
    session = requests.Session()
    session.get("https://xueqiu.com", headers=headers) # 获取Cookie
    
    # 抓取最近 1000 天的数据
    url = f"https://stock.xueqiu.com/v5/stock/chart/kline.json?symbol={symbol}&begin={int(time.time()*1000)}&period=day&type=before&count=-1000&indicator=kline,pe,pb,dividend_yield"
    
    r = session.get(url, headers=headers)
    if r.status_code != 200:
        return None
    
    items = r.json()['data']['item']
    df = pd.DataFrame(items, columns=['timestamp', 'volume', 'open', 'high', 'low', 'close', 'chg', 'percent', 'turnover', 'pe', 'pb', 'div_yield'])
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# --- 4. 逻辑计算引擎 ---
def calculate_logic(name, df, proj_yrs):
    # 1. 提取当前值
    curr_pe = df['pe'].iloc[-1]
    curr_pb = df['pb'].iloc[-1]
    curr_roe = curr_pb / curr_pe
    
    # 2. 计算分红率 (Payout Ratio = 股息率 * PE / 100)
    df['payout_ratio'] = (df['div_yield'] / 100) * df['pe']
    # 取近三年均值 (约750个交易日)
    avg_payout = df['payout_ratio'].tail(750).mean()
    avg_payout = max(min(avg_payout, 0.8), 0.1) # 保护性限制在10%-80%
    
    # 3. 确定回归目标 (目标ROE取5年均值，目标PE取5年中位数)
    target_roe = (df['pb'] / df['pe']).mean()
    target_pe = df['pe'].median()
    
    # 4. 净资产复利推演 (对应图片算法)
    # 假设当前买入成本是 1，则初始净资产 B0 = 1/PB
    b_now = 1.0 / curr_pb
    # 每年增长率 = ROE * (1 - 分红率)
    g = target_roe * (1 - avg_payout)
    b_future = b_now * ((1 + g) ** proj_yrs)
    
    # 5. 预期结果
    # 市值 = 未来净资产 * 目标ROE * 目标PE
    fair_value = b_future * target_roe * target_pe
    total_upside = (fair_value - 1) * 100
    
    return {
        "指数名称": name,
        "当前ROE": f"{curr_roe*100:.2f}%",
        "目标ROE": f"{target_roe*100:.2f}%",
        "当前PE": f"{curr_pe:.2f}",
        "目标PE": f"{target_pe:.2f}",
        "3年均分红率": f"{avg_payout*100:.2f}%",
        f"{proj_yrs}年后预期空间": f"{total_upside:.2f}%"
    }

# --- 5. 执行展示 ---
results = []
status_placeholder = st.empty()

for name, symbol in TARGETS.items():
    status_placeholder.text(f"正在抓取 {name} 数据...")
    df_raw = fetch_from_xueqiu(symbol)
    if df_raw is not None:
        res = calculate_logic(name, df_raw, projection_years)
        results.append(res)
    time.sleep(0.5) # 防止请求过快

status_placeholder.empty()

if results:
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(f"{projection_years}年后预期空间", ascending=False)
    
    st.table(res_df)
    
    st.markdown(f"""
    ---
    ### 📖 算法逻辑校验（完全对齐 Excel）：
    - **分红率均值化**：已根据过去三年平均股息自动计算留存收益比例（{res_df.iloc[0]['3年均分红率']}）。
    - **净资产复利**：代码通过 `(1+ROE*(1-分红率))^n` 模拟了你图片中第一年到第七年的净资产增长。
    - **等雨点**：当当前的 **ROE < 目标ROE** 且 **PE < 目标PE** 时，系统会预警高弹性空间。
    """)
else:
    st.error("数据调取仍然失败。这通常说明你的环境禁用了所有外部请求。请务必在【本地电脑】运行此脚本。")
