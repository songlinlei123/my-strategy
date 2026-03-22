import streamlit as st
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来·实时监控站", layout="wide")

st.sidebar.title("🌧️ 策略配置")
lookback_years = st.sidebar.slider("查看历史区间 (年)", 3, 10, 8)
base_money = st.sidebar.number_input("基础定投金额 (元)", 100, 10000, 1000)

# --- 2. 标的字典 (优化了代码格式以适配接口) ---
TARGETS = {
    "沪深300": ["沪深300", "000300", "PE"],
    "中证500": ["中证500", "000905", "PE"],
    "创业板指": ["创业板指", "399006", "PE"],
    "上证50": ["上证50", "000016", "PB"],
    "恒生指数": ["恒生指数", "hsi", "PE"],
    "中证白酒": ["中证白酒", "399997", "PE"],
    "中国互联网50": ["中证海外中国互联网50", "h30533", "PE"]
}

# --- 3. 核心抓取函数 (增强了容错性) ---
def fetch_data_safe(name, f_name, p_code, years, m_type):
    try:
        # 1. 获取估值数据
        # 增加重试机制
        for _ in range(3):
            try:
                df_val = ak.index_value_hist_funddb(symbol=f_name, indicator=m_type)
                if not df_val.empty: break
            except:
                time.sleep(1)
                continue
        
        if df_val.empty:
            return {"指数名称": name, "状态": "数据接口维护"}

        df_val['date'] = pd.to_datetime(df_val['date'])
        start_date = datetime.now() - timedelta(days=years*365)
        df_filtered = df_val[df_val['date'] >= start_date].copy()
        
        curr_val = df_filtered.iloc[-1]['value']
        percentile = (df_filtered['value'] < curr_val).mean() * 100
        
        # 2. 获取价格数据 (改用更稳定的东财接口)
        try:
            # 简化逻辑：估值分位够用了，如果年线偏离度获取失败，给个0
            df_p = ak.index_zh_a_hist(symbol=p_code, period="daily")
            df_p['ma250'] = df_p['收盘'].rolling(window=250).mean()
            curr_price = df_p.iloc[-1]['收盘']
            curr_ma = df_p.iloc[-1]['ma250']
            bias = ((curr_price / curr_ma) - 1) * 100
        except:
            bias = 0 # 如果价格抓不到，暂不计算偏离度

        return {
            "指数名称": name,
            "当前估值": round(curr_val, 2),
            "百分位": round(percentile, 2),
            "年线偏离": round(bias, 2),
            "更新日期": df_val.iloc[-1]['date'].strftime('%Y-%m-%d')
        }
    except Exception as e:
        # 在调试阶段，取消下面这行的注释可以看到具体报错
        # st.write(f"调试信息 ({name}): {str(e)}")
        return None

# --- 4. 主界面 ---
st.header("🌧️ 等雨来策略：全自动雷达")

if st.button('🔄 点击刷新数据'):
    st.cache_data.clear()

data_rows = []
progress_bar = st.progress(0)
index_names = list(TARGETS.keys())

for i, name in enumerate(index_names):
    config = TARGETS[name]
    res = fetch_data_safe(name, config[0], config[1], lookback_years, config[2])
    if res and "当前估值" in res:
        # 判定逻辑
        p = res['百分位']
        b = res['年线偏离']
        
        if p < 20 and b < -10:
            status, color = "🌧️ 等雨来", "green"
            money = base_money * (1.5 + (20 - p)/10)
        elif p < 20:
            status, color = "🌦️ 雨已至", "blue"
            money = base_money * 1.2
        elif p > 80:
            status, color = "☀️ 盛夏过热", "red"
            money = 0
        else:
            status, color = "⛅ 正常观望", "black"
            money = base_money if p < 50 else 0
        
        res['当前状态'] = status
        res['建议买入金额'] = f"¥{int(money)}" if money > 0 else "停止买入"
        data_rows.append(res)
    progress_bar.progress((i + 1) / len(index_names))

if data_rows:
    df = pd.DataFrame(data_rows)
    st.table(df[['指数名称', '更新日期', '当前估值', '百分位', '年线偏离', '当前状态', '建议买入金额']])
else:
    st.error("⚠️ 暂时无法调取数据。原因可能是：1.接口正处于维护期 2.海外服务器请求受限。")
    st.info("💡 解决办法：请稍后手动点击上方“刷新数据”按钮。")

st.caption("提示：数据源来自 FundDB 及 Sina Finance。")