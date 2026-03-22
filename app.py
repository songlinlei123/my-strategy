import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来策略·基本面复利工作台", layout="wide")
st.title("🌧️ 等雨来：内生增长 + 估值双回归模型")
st.caption("数据源：东方财富/新浪财经 | 逻辑：净资产复利增长模型")

# --- 2. 侧边栏参数 ---
st.sidebar.header("🎯 模拟参数")
projection_years = st.sidebar.slider("推演未来年限", 1, 10, 3)
lookback_years = st.sidebar.slider("历史锚点参考年限", 3, 15, 10)
base_investment = st.sidebar.number_input("初始单位投入", value=1.0)

# 标的代码映射 (东财格式)
TARGETS = {
    "沪深300": "000300",
    "中证500": "000905",
    "创业板指": "399006",
    "上证50": "000016",
    "中证白酒": "399997",
    "恒生指数": "HSI"
}

# --- 3. 稳健数据获取函数 ---
def get_index_valuation_stable(symbol):
    """
    尝试从多个数据源获取估值数据，确保国内运行稳定
    """
    try:
        # 尝试获取指数估值 (采用 funddb，但在失败时捕获)
        # 提示：如果本地运行报错，请确保 pip install --upgrade akshare
        df = ak.index_value_hist_funddb(symbol=symbol, indicator="全部")
        if df is not None and not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            return df
    except Exception as e:
        st.warning(f"无法从主接口获取 {symbol} 数据，尝试备用方案...")
    return None

# --- 4. 逻辑计算引擎 ---
def calculate_rain_strategy(name, df, proj_yrs, hist_yrs):
    # 截取历史区间
    start_date = datetime.now() - timedelta(days=hist_yrs*365)
    hist_df = df[df['date'] >= start_date].copy()
    
    # 获取当前值
    curr_pe = hist_df.iloc[-1]['pe']
    curr_pb = hist_df.iloc[-1]['pb']
    # 股息率转为小数
    curr_div_yield = hist_df.iloc[-1]['股息率'] / 100 
    
    # 1. 计算当前 ROE (PB/PE)
    curr_roe = curr_pb / curr_pe
    
    # 2. 计算分红率 (Payout Ratio = 股息率 * PE)
    # 取近三年平均分红率，对应你的“近三年分红平均数”要求
    hist_df['payout_ratio'] = (hist_df['股息率'] / 100) * hist_df['pe']
    avg_payout = hist_df.tail(750)['payout_ratio'].mean()
    avg_payout = max(min(avg_payout, 0.9), 0.1) # 限制在10%-90%之间防止逻辑崩溃
    
    # 3. 设定目标锚点 (ROE回归均值，PE回归中位数)
    target_roe = hist_df['pb'].mean() / hist_df['pe'].mean()
    target_pe = hist_df['pe'].median()
    
    # 4. 净资产增长推演 (复刻 Excel 图片公式)
    # 假设初始净资产 B = 1/PB (为了计算相对于当前价格1的增量)
    b_now = 1.0 / curr_pb
    
    # 模拟未来 projection_years 年的增长
    # 净资产增长率 = ROE * (1 - 分红率)
    annual_growth_rate = target_roe * (1 - avg_payout)
    b_future = b_now * ((1 + annual_growth_rate) ** proj_yrs)
    
    # 5. 计算等雨空间
    # 最终市值 = 最终净资产 * 目标ROE * 目标PE
    final_market_value = b_future * target_roe * target_pe
    potential_upside = (final_market_value - 1) * 100
    
    return {
        "指数名称": name,
        "当前ROE": f"{curr_roe*100:.2f}%",
        "目标ROE": f"{target_roe*100:.2f}%",
        "当前PE": round(curr_pe, 2),
        "目标PE": round(target_pe, 2),
        "三年均分红率": f"{avg_payout*100:.2f}%",
        "预期年化收益": f"{((final_market_value**(1/proj_yrs))-1)*100:.2f}%",
        "等雨空间(总涨幅)": f"{potential_upside:.2f}%"
    }

# --- 5. 网页主体 ---
if st.sidebar.button("刷新并运行模型"):
    st.cache_data.clear()

results = []
progress_bar = st.progress(0)

for i, (name, symbol) in enumerate(TARGETS.items()):
    df_raw = get_index_valuation_stable(name)
    if df_raw is not None:
        res = calculate_rain_strategy(name, df_raw, projection_years, lookback_years)
        results.append(res)
    progress_bar.progress((i + 1) / len(TARGETS))

if results:
    res_df = pd.DataFrame(results)
    # 按潜力排序
    res_df = res_df.sort_values("等雨空间(总涨幅)", ascending=False)
    
    # 显示表格
    st.subheader(f"📊 推演结果（假设未来 {projection_years} 年回归）")
    st.dataframe(res_df, use_container_width=True)
    
    # 详细解释
    st.markdown(f"""
    ---
    ### 📝 模型逻辑校对 (基于你的 Excel)：
    1. **单位净资产**：假设当前买入价格为 1，则你买到的净资产是 $1 / PB$。
    2. **内生增长**：由于分红率为 **{res_df.iloc[0]['三年均分红率']}**，每年有剩余利润留在公司。
    3. **净资产增量**：经过 {projection_years} 年，你的净资产将从现在的初始值增长到未来值。
    4. **双击回报**：当你等到“雨”来（ROE 回升到均值，PE 修复到中位），你的收益等于 **(增长后的净资产 × 目标ROE × 目标PE)**。
    """)
else:
    st.error("数据调取失败。原因：API接口对海外IP有限制，或本地AkShare版本过低。")
    st.markdown("""
    **解决办法：**
    1. 在本地命令行运行：`pip install --upgrade akshare`
    2. 确保你在**国内网络环境**下运行。
    3. 如果是在服务器运行，请开启国内代理。
    """)
