import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来·基本面复利雷达", layout="wide")
st.title("🌧️ 等雨来：内生增长 + 估值双回归模型")
st.caption("数据源：实时爬取国内金融门户 (东财/新浪) | 逻辑：净资产复利 + ROE回归 + PE修复")

# --- 2. 策略参数 ---
st.sidebar.header("🎯 模型参数")
projection_years = st.sidebar.slider("预期等待年限 (雨季长度)", 1, 7, 3)
lookback_years = st.sidebar.slider("历史锚点参考年限", 5, 15, 10)
base_money = st.sidebar.number_input("初始投入基准", value=1000)

# 指数列表 (采用东财代码，国内访问最稳)
TARGETS = {
    "沪深300": "000300",
    "中证500": "000905",
    "创业板指": "399006",
    "上证50": "000016",
    "深证成指": "399001",
    "恒生指数": "HSI",
}

# --- 3. 国内源稳健爬取函数 ---
@st.cache_data(ttl=3600*12)
def fetch_stable_data(symbol):
    try:
        # 使用乐咕/东财等国内镜像源接口，避开海外IP封锁
        # 获取指数估值历史数据
        df = ak.index_value_hist_funddb(symbol=symbol, indicator="全部") 
        # 如果 funddb 依然受限，此处可替换为 ak.index_valuation_zh_cn() 等其他国内源
        
        df['date'] = pd.to_datetime(df['date'])
        # 核心指标提取
        df = df[['date', 'pe', 'pb', '股息率']]
        df.columns = ['date', 'pe', 'pb', 'div_yield']
        
        # 计算 ROE 和 分红率 (Payout Ratio)
        df['roe'] = (df['pb'] / df['pe']) # 这里的ROE为小数形式
        df['payout_ratio'] = (df['div_yield'] / 100) * df['pe'] # 分红率 = 股息率 * PE
        
        return df
    except Exception as e:
        return None

# --- 4. 逻辑推演引擎 ---
results = []
progress_bar = st.progress(0)

for i, (name, code) in enumerate(TARGETS.items()):
    df = fetch_stable_data(name)
    if df is not None and not df.empty:
        # 截取历史区间用于计算锚点
        start_date = datetime.now() - timedelta(days=lookback_years*365)
        hist_df = df[df['date'] >= start_date].copy()
        
        # 1. 当前值
        curr_pe = hist_df.iloc[-1]['pe']
        curr_pb = hist_df.iloc[-1]['pb']
        curr_roe = hist_df.iloc[-1]['roe']
        
        # 2. 计算近三年平均分红率 (排除异常值)
        recent_3y = hist_df.tail(750)
        avg_payout_3y = recent_3y['payout_ratio'].clip(0, 1).mean() 
        
        # 3. 确定回归目标 (目标ROE取均值，目标PE取中位数)
        target_roe = hist_df['roe'].mean()
        target_pe = hist_df['pe'].median()
        
        # 4. 净资产复利推演 (对应图片算法)
        # 初始净资产 (B0) 归一化为 1/PB
        b_start = 1.0 / curr_pb
        # 每年增长率 g = 目标ROE * (1 - 分红率)
        annual_g = target_roe * (1 - avg_payout_3y)
        b_future = b_start * ((1 + annual_g) ** projection_years)
        
        # 5. 计算未来合理市值 (P = B_future * ROE_target * PE_target)
        fair_value = b_future * target_roe * target_pe
        total_growth = (fair_value - 1) * 100
        
        results.append({
            "指数名称": name,
            "当前ROE": f"{curr_roe*100:.2f}%",
            "目标ROE": f"{target_roe*100:.2f}%",
            "当前PE": round(curr_pe, 2),
            "目标PE": round(target_pe, 2),
            "3年平均分红率": f"{avg_payout_3y*100:.2f}%",
            f"{projection_years}年后预期空间": f"{total_growth:.2f}%",
            "建议动作": "🌧️ 等雨来" if total_growth > 50 else "🌤️ 观望"
        })
    progress_bar.progress((i + 1) / len(TARGETS))

# --- 5. 结果展示 ---
if results:
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(f"{projection_years}年后预期空间", ascending=False)
    
    st.subheader(f"📊 基于 {lookback_years} 年历史数据的复利模型扫描")
    
    # 样式美化
    def color_growth(val):
        color = 'green' if float(val.replace('%','')) > 50 else 'black'
        return f'color: {color}'

    st.table(res_df.style.applymap(color_growth, subset=[f"{projection_years}年后预期空间"]))

    st.markdown(f"""
    ---
    ### 📖 算法逻辑校验（严格对齐 Excel）：
    - **净资产底座**：我们假设当前价格为 1，则账面价值为 $1/PB$。
    - **内生增长**：假设每年企业赚取的利润，在扣除 **{results[0]['3年平均分红率'] if results else '38%'}** 的分红后，全部留存。
    - **等雨时刻**：当市场 ROE 从当前的低谷回归到历史平均水平，且 PE 从低估回归到中位数时，**复利 + 盈利回升 + 估值修复** 三者相乘。
    - **避坑提示**：如果一个指数 ROE 极低且分红率极高，其净资产几乎不增长，此时只能干等 PE 修复。
    """)
else:
    st.error("无法获取数据。请尝试在本地运行，或检查 `akshare` 库是否为最新版本。")
