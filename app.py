import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来策略·基本面雷达", layout="wide")
st.title("🌧️ 等雨来：内生增长 + 估值双回归模型")
st.caption("逻辑：净资产复利增长 + ROE回归 + PE修复 | 数据源：雪球实时接口")

# --- 2. 侧边栏设置 ---
st.sidebar.header("🎯 模拟参数")
proj_years = st.sidebar.slider("推演未来年限 (n)", 1, 10, 3)
lookback_days = st.sidebar.slider("历史参考天数", 250, 1500, 750)
base_money = st.sidebar.number_input("初始投入基准", value=1000)

# 指数列表 (雪球格式)
TARGETS = {
    "沪深300": "SH000300",
    "中证500": "SH000905",
    "创业板指": "SZ399006",
    "上证50": "SH000016",
    "中证白酒": "SZ399997",
    "恒生指数": "HKHSI"
}

# --- 3. 改进的雪球抓取函数 (带容错) ---
def fetch_xueqiu_data(name, symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://xueqiu.com"
    }
    session = requests.Session()
    try:
        # 1. 必须先访问主页获取Cookie
        session.get("https://xueqiu.com", headers=headers, timeout=15)
        
        # 2. 抓取K线及估值 (PE, PB, 股息率)
        # count=-1000 代表抓取最近1000条数据
        url = f"https://stock.xueqiu.com/v5/stock/chart/kline.json?symbol={symbol}&begin={int(time.time()*1000)}&period=day&type=before&count=-1000&indicator=kline,pe,pb,dividend_yield"
        
        r = session.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            json_data = r.json()
            if 'data' in json_data and 'item' in json_data['data']:
                items = json_data['data']['item']
                df = pd.DataFrame(items, columns=['timestamp', 'volume', 'open', 'high', 'low', 'close', 'chg', 'percent', 'turnover', 'pe', 'pb', 'div_yield'])
                return df
            else:
                st.warning(f"{name} 接口返回数据结构异常")
        else:
            st.error(f"{name} 请求失败，状态码: {r.status_code}")
    except Exception as e:
        st.error(f"{name} 获取失败: {str(e)}")
    return None

# --- 4. 核心逻辑 (严格对齐图片算法) ---
def run_model(name, df, n):
    # 提取最新一条数据
    latest = df.iloc[-1]
    curr_pe = latest['pe']
    curr_pb = latest['pb']
    curr_div = latest['div_yield'] if latest['div_yield'] else 0
    
    # A. 当前ROE (PB/PE)
    curr_roe = curr_pb / curr_pe if curr_pe > 0 else 0
    
    # B. 近三年平均分红率 (Dividend_Yield * PE / 100)
    df['payout'] = (df['div_yield'] / 100) * df['pe']
    avg_payout = df['payout'].tail(750).mean() # 约3年均值
    avg_payout = max(min(avg_payout, 0.8), 0.1) # 保护性区间
    
    # C. 历史锚点 (ROE均值，PE中位数)
    target_roe = (df['pb'] / df['pe']).replace([np.inf, -np.inf], np.nan).dropna().mean()
    target_pe = df['pe'].replace([0, np.inf, -np.inf], np.nan).dropna().median()
    
    # D. 复利增长推演 (图片逻辑)
    # 1. 初始净资产 B0 = 1 / PB
    b_now = 1.0 / curr_pb if curr_pb > 0 else 0
    # 2. 每年内生增长率 g = ROE * (1 - 分红率)
    g = target_roe * (1 - avg_payout)
    b_future = b_now * ((1 + g) ** n)
    
    # E. 未来预期市值 = 未来净资产 * 目标ROE * 目标PE
    fair_value = b_future * target_roe * target_pe
    upside = (fair_value - 1) * 100
    
    return {
        "指数名称": name,
        "当前ROE": f"{curr_roe*100:.2f}%",
        "目标ROE": f"{target_roe*100:.2f}%",
        "当前PE": f"{curr_pe:.2f}",
        "目标PE": f"{target_pe:.2f}",
        "3年均分红率": f"{avg_payout*100:.2f}%",
        f"{n}年后预期空间": f"{upside:.2f}%",
        "建议买入": f"¥ {int(base_money * (upside/100 + 1))}" if upside > 0 else "观望"
    }

# --- 5. 主页面自动运行逻辑 ---
st.subheader("📊 策略扫描结果")
results = []

# 创建一个进度条
progress_bar = st.progress(0)
status_text = st.empty()

# 自动开始循环
index_names = list(TARGETS.keys())
for i, name in enumerate(index_names):
    status_text.text(f"正在同步 {name} 的基本面数据...")
    df_raw = fetch_xueqiu_data(name, TARGETS[name])
    
    if df_raw is not None and not df_raw.empty:
        try:
            res = run_model(name, df_raw, proj_years)
            results.append(res)
        except Exception as e:
            st.error(f"{name} 计算逻辑错误: {e}")
    
    # 更新进度条
    progress_bar.progress((i + 1) / len(index_names))
    time.sleep(0.5) # 避免请求过快被雪球暂时封禁

status_text.empty()

# --- 6. 结果展示 ---
if results:
    final_df = pd.DataFrame(results)
    # 按潜力空间排序
    final_df = final_df.sort_values(f"{proj_years}年后预期空间", ascending=False)
    
    st.table(final_df)
    
    st.success("✅ 数据抓取完成！")
    st.markdown(f"""
    ---
    ### 📖 算法说明：
    - **为什么能“等雨来”？** 因为你现在的 **ROE ({results[0]['当前ROE']})** 低于历史平均，且 **PE ({results[0]['当前PE']})** 低于中值。
    - **关于增长**：模型已自动提取近三年的分红数据。如果分红率低，净资产增长会更快；如果分红率高，则更看重估值修复。
    - **计算公式**：$市值 = (1/当前PB) \\times (1 + ROE_{目标} \\times (1-分红率))^n \\times ROE_{目标} \\times PE_{目标}$
    """)
else:
    st.error("❌ 无法获取任何结果。请检查你的网络连接，或确认雪球网（xueqiu.com）在你的服务器环境下可以访问。")

if st.button("🔄 手动刷新"):
    st.rerun()
