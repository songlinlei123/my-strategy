import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来·真实数据看板", layout="wide")
st.title("🌧️ 等雨来：实时 PE-TTM 与 10 年分位监控")
st.caption("数据说明：实时抓取 A 股/港股 PE 序列，动态计算 10 年分位值，拒绝静态假数据。")

# --- 2. 侧边栏参数 ---
st.sidebar.header("🎯 策略推演参数")
n_years = st.sidebar.slider("推演未来年限 (n)", 1, 10, 3)
st.sidebar.markdown("---")

# 指数列表与基本面锚点 (ROE 和 Payout 相对稳定，PE 动态抓取)
TARGETS = {
    "沪深300": {"symbol": "SH000300", "t_roe": 0.11, "payout": 0.35},
    "中证500": {"symbol": "SH000905", "t_roe": 0.08, "payout": 0.22},
    "创业板指": {"symbol": "SZ399006", "t_roe": 0.12, "payout": 0.15},
    "上证50":   {"symbol": "SH000016", "t_roe": 0.10, "payout": 0.40},
    "中证红利": {"symbol": "SH000922", "t_roe": 0.12, "payout": 0.55},
    "恒生指数": {"symbol": "HKHSI",    "t_roe": 0.09, "payout": 0.45},
}

# --- 3. 动态数据抓取引擎 ---
@st.cache_data(ttl=3600) # 每小时更新一次
def fetch_real_data(name, symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/00.1",
        "Referer": "https://xueqiu.com"
    }
    session = requests.Session()
    try:
        # 1. 访问雪球获取基础Cookie
        session.get("https://xueqiu.com", headers=headers, timeout=10)
        
        # 2. 抓取过去 10 年的日线数据 (约 2500 天)
        # count=-2500 代表最近10年
        url = f"https://stock.xueqiu.com/v5/stock/chart/kline.json?symbol={symbol}&begin={int(time.time()*1000)}&period=day&type=before&count=-2500&indicator=kline,pe,pb"
        
        r = session.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        
        items = r.json()['data']['item']
        df = pd.DataFrame(items, columns=['timestamp', 'volume', 'open', 'high', 'low', 'close', 'chg', 'percent', 'turnover', 'pe', 'pb'])
        
        # 剔除无效 PE (<=0)
        pe_series = df[df['pe'] > 0]['pe'].tolist()
        if not pe_series: return None
        
        # 3. 计算实时指标
        curr_pe = pe_series[-1] # 最新的 PE-TTM
        curr_pb = df['pb'].iloc[-1]
        
        # 4. 计算 10 年 PE 百分位 (真实分位值)
        # 逻辑：当前PE在过去10年中高于多少比例的交易日
        smaller_count = sum(1 for p in pe_series if p < curr_pe)
        percentile = (smaller_count / len(pe_series)) * 100
        
        return {
            "curr_pe": curr_pe,
            "curr_pb": curr_pb,
            "percentile": percentile,
            "pe_50": np.median(pe_series),
            "pe_20": np.percentile(pe_series, 20),
            "pe_80": np.percentile(pe_series, 80)
        }
    except Exception as e:
        return None

# --- 4. 核心计算逻辑 (对齐 Excel) ---
def run_analysis():
    results = []
    progress_bar = st.progress(0)
    
    for i, (name, config) in enumerate(TARGETS.items()):
        data = fetch_real_data(name, config['symbol'])
        
        if data:
            # 公式推演：ROI = [(1+g)^n * (目标PE/当前PE) * (目标ROE/当前ROE)] - 1
            # 假设回归至 50% 分位 PE
            t_pe = data['pe_50']
            t_roe = config['t_roe']
            g = t_roe * (1 - config['payout'])
            
            # ROI 1: 回归到中位数的纯收益率
            # 假设当前ROE较目标略有折价 (0.9) 作为干旱期
            future_val_50 = ((1 + g) ** n_years) * (t_pe / data['curr_pe']) * (1 / 0.9)
            roi_50 = (future_value_50 - 1) * 100 if 'future_value_50' in locals() else ((((1 + g) ** n_years) * (t_pe / data['curr_pe']) / 0.9) - 1) * 100
            
            results.append({
                "指数名称": name,
                "当前 PE-TTM": round(data['curr_pe'], 2),
                "10年 PE 分位": f"{data['percentile']:.1f}%",
                "10年 PE 中位": round(data['pe_50'], 2),
                "ROE 锚点": f"{t_roe*100:.1f}%",
                "当前状态": "☀️ 过热" if data['percentile'] > 80 else ("🌧️ 等雨" if data['percentile'] < 20 else "⛅ 观望"),
                f"{n_years}年后预期收益(中位)": f"{roi_50:.1f}%"
            })
        
        progress_bar.progress((i + 1) / len(TARGETS))

    if results:
        res_df = pd.DataFrame(results)
        st.table(res_df.style.applymap(lambda x: 'color: red' if '过热' in str(x) else ('color: green' if '等雨' in str(x) else ''), subset=['当前状态']))
    else:
        st.error("数据调取异常：海外服务器抓取国内实时 PE 失败，请检查雪球 API 状态。")

# --- 5. 执行 ---
run_analysis()

st.markdown(f"""
---
### 🧪 逻辑验证报告
1. **真实性**：程序实时下载了过去 2500 个交易日的 PE 数据。
2. **百分位算法**：
   - 如果当前 PE = 35，且过去 2500 天里有 2175 天的 PE 小于 35。
   - 则百分位 = $2175 / 2500 = 87\%$。
3. **收益率公式**：
   - 考虑了 PE 的回归压力。例如**中证500**，如果当前 PE (35) 远高于中位 ({TARGETS['中证500'].get('t_pe','未知')} 左右)，那么其预期收益会被估值下杀大幅对冲。
""")
