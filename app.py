import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来·基本面复利工作台", layout="wide")
st.title("🌧️ 等雨来：内生增长 + 估值双回归模型")
st.caption("数据源：雪球实时接口 | 逻辑：净资产复利 + ROE回归 + PE修复")

# --- 2. 侧边栏参数 ---
st.sidebar.header("🎯 模拟参数")
proj_years = st.sidebar.slider("推演未来年限 (n)", 1, 10, 3)
lookback_days = st.sidebar.slider("历史参考天数 (用于锚点计算)", 250, 1500, 750)
base_investment = st.sidebar.number_input("初始单位投入", value=1.0)

# 指数列表 (雪球格式)
TARGETS = {
    "沪深300": "SH000300",
    "中证500": "SH000905",
    "创业板指": "SZ399006",
    "上证50": "SH000016",
    "中证白酒": "SZ399997",
    "恒生指数": "HKHSI"
}

# --- 3. 稳健的雪球数据抓取函数 ---
def fetch_xueqiu_stable(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://xueqiu.com"
    }
    session = requests.Session()
    try:
        # 获取基础Cookie
        session.get("https://xueqiu.com", headers=headers, timeout=10)
        # 抓取历史估值数据
        url = f"https://stock.xueqiu.com/v5/stock/chart/kline.json?symbol={symbol}&begin={int(time.time()*1000)}&period=day&type=before&count=-1000&indicator=kline,pe,pb,dividend_yield"
        r = session.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()['data']['item']
            df = pd.DataFrame(data, columns=['timestamp', 'volume', 'open', 'high', 'low', 'close', 'chg', 'percent', 'turnover', 'pe', 'pb', 'div_yield'])
            return df
    except Exception as e:
        st.error(f"连接雪球失败: {e}")
    return None

# --- 4. 核心逻辑引擎 (对齐 Excel 图片) ---
def calculate_growth_model(name, df, n_years):
    # 1. 提取当前值
    latest = df.iloc[-1]
    curr_pe = latest['pe']
    curr_pb = latest['pb']
    curr_div_yield = latest['div_yield'] if latest['div_yield'] else 0
    
    # 2. 计算当前 ROE = PB / PE
    curr_roe = curr_pb / curr_pe if curr_pe > 0 else 0
    
    # 3. 计算三年平均分红率 (Payout Ratio = 股息率 * PE / 100)
    df['payout_ratio'] = (df['div_yield'] / 100) * df['pe']
    avg_payout = df['payout_ratio'].tail(750).mean() # 取近3年均值
    avg_payout = max(min(avg_payout, 0.8), 0.1) # 保护性限制
    
    # 4. 设定回归目标 (ROE均值，PE中位数)
    target_roe = (df['pb'] / df['pe']).mean()
    target_pe = df['pe'].median()
    
    # 5. 净资产复利推演 (复刻 Excel 公式)
    # 初始净资产 B0 = 1 / PB (相对于当前买入价1)
    b_now = 1.0 / curr_pb
    # 每年内生增长率 g = 预期ROE * (1 - 分红率)
    annual_g = target_roe * (1 - avg_payout)
    b_future = b_now * ((1 + annual_g) ** n_years)
    
    # 6. 未来合理市值 = 未来净资产 * 目标ROE * 目标PE
    fair_market_value = b_future * target_roe * target_pe
    potential_upside = (fair_market_value - 1) * 100
    
    return {
        "指数名称": name,
        "当前ROE": f"{curr_roe*100:.2f}%",
        "目标ROE": f"{target_roe*100:.2f}%",
        "当前PE": f"{curr_pe:.2f}",
        "目标PE": f"{target_pe:.2f}",
        "3年均分红率": f"{avg_payout*100:.2f}%",
        f"{n_years}年后预期涨幅": f"{potential_upside:.2f}%",
        "年化预期": f"{((fair_market_value**(1/n_years))-1)*100:.2f}%" if fair_market_value > 0 else "N/A"
    }

# --- 5. 页面展示逻辑 ---
results = []
if st.button("🚀 实时扫描全市场"):
    with st.spinner('正在通过雪球云端接口抓取基本面数据...'):
        for name, symbol in TARGETS.items():
            df_raw = fetch_xueqiu_stable(symbol)
            if df_raw is not None and not df_raw.empty:
                res = calculate_growth_model(name, df_raw, proj_years)
                results.append(res)
            time.sleep(0.3) # 友好抓取

if results:
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(f"{proj_years}年后预期涨幅", ascending=False)
    
    st.subheader(f"📊 基于 {proj_years} 年复利增长的推演结果")
    st.dataframe(
        res_df.style.apply(lambda x: ['background-color: #e6f3ff' if float(str(v).replace('%','')) > 50 else '' for v in x], axis=1),
        use_container_width=True
    )
    
    st.markdown(f"""
    ---
    ### 📝 模型逻辑校对：
    - **单位净资产**：我们假设你现在花 1 块钱买入，你买到的账面净资产是 $1/PB$。
    - **内生增长**：由于分红率为 **{res_df.iloc[0]['3年均分红率']}**，每年剩余利润留存，净资产会逐年滚雪球。
    - **等雨逻辑**：收益 = **净资产变大 × 盈利能力修复(ROE) × 估值修复(PE)**。这三者在同一时间点发生的概率，就是你的“等雨来”时刻。
    """)
else:
    st.write("点击上方按钮开始实时计算。")
