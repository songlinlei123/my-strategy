import streamlit as st
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

# --- 1. 页面设置 ---
st.set_page_config(page_title="等雨来·实时监控站", layout="wide")

# 侧边栏：配置参数
st.sidebar.title("🌧️ 策略配置")
lookback_years = st.sidebar.slider("查看历史区间 (年)", 3, 10, 5)
base_money = st.sidebar.number_input("基础定投金额 (元)", 100, 10000, 1000)

# --- 2. 标的字典 (代码经过核对，确保能抓到数据) ---
# 格式: 名称: [FundDB名称, 价格接口代码, 指标类型]
TARGETS = {
    "沪深300": ["沪深300", "sh000300", "PE"],
    "中证500": ["中证500", "sh000905", "PE"],
    "创业板指": ["创业板指", "sz399006", "PE"],
    "上证50": ["上证50", "sh000016", "PB"],
    "恒生指数": ["恒生指数", "hkHSI", "PE"],
    "中证白酒": ["中证白酒", "sz399997", "PE"],
    "中国互联网50": ["中证海外中国互联网50", "shH30533", "PE"]
}

# --- 3. 数据抓取与计算逻辑 ---
@st.cache_data(ttl=3600) # 每一小时刷新一次缓存，确保数据是当天的
def get_market_data(name, f_name, p_code, years, m_type):
    try:
        # 获取估值历史 (FundDB数据源更新至上一交易日)
        df_val = ak.index_value_hist_funddb(symbol=f_name, indicator=m_type)
        df_val['date'] = pd.to_datetime(df_val['date'])
        
        # 截取选定年限的数据
        start_date = datetime.now() - timedelta(days=years*365)
        df_filtered = df_val[df_val['date'] >= start_date].copy()
        
        curr_val = df_filtered.iloc[-1]['value']
        percentile = (df_filtered['value'] < curr_val).mean() * 100
        last_date = df_filtered.iloc[-1]['date'].strftime('%Y-%m-%d')

        # 获取价格与年线偏离度
        if "hk" in p_code:
            df_p = ak.stock_hk_index_daily_sina(symbol=p_code.replace("hk", ""))
        else:
            df_p = ak.stock_zh_index_daily(symbol=p_code)
        
        df_p['ma250'] = df_p['close'].rolling(window=250).mean()
        curr_price = df_p.iloc[-1]['close']
        curr_ma = df_p.iloc[-1]['ma250']
        bias = (curr_price / curr_ma - 1) * 100
        
        return {
            "指数名称": name,
            "更新日期": last_date,
            "当前估值": round(curr_val, 2),
            "百分位": round(percentile, 2),
            "年线偏离": round(bias, 2),
            "指标": m_type
        }
    except Exception as e:
        return None

# --- 4. 网页界面构建 ---
st.header("🌧️ 等雨来策略：全市场自动雷达")
st.write(f"本页面自动获取最新交易日数据。当前参考周期：{lookback_years}年。")

data_rows = []
with st.spinner('正在同步最新交易信息...'):
    for name, config in TARGETS.items():
        res = get_market_data(name, config[0], config[1], lookback_years, config[2])
        if res:
            # 状态判定逻辑
            if res['百分位'] < 20 and res['年线偏离'] < -10:
                status = "🌧️ 枯水待雨"
                money = base_money * (1.5 + (20 - res['百分位'])/10)
            elif res['百分位'] < 20 and res['年线偏离'] >= -10:
                status = "🌦️ 雨已至"
                money = base_money * 1.2
            elif res['百分位'] > 80:
                status = "☀️ 盛夏过热"
                money = 0
            else:
                status = "⛅ 正常观望"
                money = base_money if res['百分位'] < 50 else 0
            
            res['当前状态'] = status
            res['建议买入金额'] = f"¥{int(money)}" if money > 0 else "停止买入"
            data_rows.append(res)

if data_rows:
    df = pd.DataFrame(data_rows)
    # 按照百分位排序，把最值得买的放前面
    df = df.sort_values("百分位", ascending=True)
    
    # 漂亮地展示表格
    st.table(df)
    
    # 核心信号提醒
    signals = df[df['当前状态'].str.contains("雨")]
    if not signals.empty:
        st.success(f"🔥 发现信号：目前有 {len(signals)} 个指数处于‘等雨来’或‘雨已至’阶段，建议关注。")
else:
    st.error("数据调取异常，请检查网络或稍后刷新。")

st.info("注：数据每日收盘后更新，建议在北京时间每晚20:00后查看最新结果。")