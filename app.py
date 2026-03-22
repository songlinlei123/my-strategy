import streamlit as st
import pandas as pd

# --- 1. 页面配置 ---
st.set_page_config(page_title="等雨来·收益率推演站", layout="wide")
st.title("🌧️ 等雨来策略：全市场基本面复利与 PE 分位推演")
st.caption("模型逻辑：净资产内生增长 + 盈利回归(ROE) + 估值(PE)分位回归")

# --- 2. 侧边栏 ---
st.sidebar.header("🎯 模拟推演参数")
n_years = st.sidebar.slider("推演未来年限 (n)", 1, 10, 3)
st.sidebar.info("计算逻辑：扣除 1.0 本金后的纯收益率。")

# --- 3. 指数分位数数据库 (近10年历史数据统计) ---
# t_roe: 目标ROE, payout: 平均分红率, pe_20/50/80: PE的20%/50%/80%分位数, curr_pe/pb: 当前估值快照
INDEX_DATA = {
    "宽基指数": {
        "沪深300": {"curr_pe": 11.8, "curr_pb": 1.28, "t_roe": 0.110, "payout": 0.35, "pe_20": 10.5, "pe_50": 12.5, "pe_80": 15.2},
        "中证500": {"curr_pe": 23.5, "curr_pb": 1.65, "t_roe": 0.080, "payout": 0.25, "pe_20": 20.2, "pe_50": 26.5, "pe_80": 33.0},
        "创业板指": {"curr_pe": 26.0, "curr_pb": 3.20, "t_roe": 0.125, "payout": 0.15, "pe_20": 28.5, "pe_50": 38.2, "pe_80": 55.0},
        "上证50":   {"curr_pe": 10.2, "curr_pb": 1.15, "t_roe": 0.105, "payout": 0.40, "pe_20": 8.8,  "pe_50": 10.5, "pe_80": 12.5},
        "中证红利": {"curr_pe": 6.8,  "curr_pb": 0.75, "t_roe": 0.115, "payout": 0.55, "pe_20": 6.2,  "pe_50": 7.5,  "pe_80": 9.5},
    },
    "行业/港股": {
        "恒生指数": {"curr_pe": 8.5,  "curr_pb": 0.88, "t_roe": 0.095, "payout": 0.45, "pe_20": 8.2,  "pe_50": 10.2, "pe_80": 12.8},
        "中证白酒": {"curr_pe": 24.5, "curr_pb": 5.50, "t_roe": 0.220, "payout": 0.50, "pe_20": 22.5, "pe_50": 30.0, "pe_80": 42.0},
        "医疗指数": {"curr_pe": 25.2, "curr_pb": 3.10, "t_roe": 0.130, "payout": 0.20, "pe_20": 26.0, "pe_50": 36.5, "pe_80": 52.0},
        "银行指数": {"curr_pe": 5.2,  "curr_pb": 0.52, "t_roe": 0.100, "payout": 0.30, "pe_20": 4.5,  "pe_50": 5.8,  "pe_80": 7.2},
        "中国互联网":{"curr_pe": 18.5, "curr_pb": 1.85, "t_roe": 0.110, "payout": 0.15, "pe_20": 16.5, "pe_50": 22.5, "pe_80": 35.0},
    }
}

# --- 4. 核心计算引擎 ---
def calculate_roi(data, target_pe, n):
    """
    计算逻辑：
    1. 初始价格 = 1.0 (本金)
    2. 初始净资产 B0 = 1 / curr_pb
    3. 每年净资产增长率 g = t_roe * (1 - payout)
    4. n年后净资产 Bn = B0 * (1+g)^n
    5. n年后利润 En = Bn * t_roe
    6. n年后市值 Pn = En * target_pe
    7. 纯收益率 = (Pn - 1.0) / 1.0
    """
    b0 = 1.0 / data['curr_pb']
    g = data['t_roe'] * (1 - data['payout'])
    bn = b0 * ((1 + g) ** n)
    en = bn * data['t_roe']
    pn = en * target_pe
    roi = (pn - 1.0) * 100
    return roi

# --- 5. 渲染表格 ---
def render_analysis():
    all_results = []
    for cat, indices in INDEX_DATA.items():
        for name, d in indices.items():
            # 计算三种分位下的纯收益率
            roi_20 = calculate_roi(d, d['pe_20'], n_years)
            roi_50 = calculate_roi(d, d['pe_50'], n_years)
            roi_80 = calculate_roi(d, d['pe_80'], n_years)
            
            all_results.append({
                "指数名称": name,
                "当前PE": d['curr_pe'],
                "平均ROE": f"{d['t_roe']*100:.1f}%",
                "20%分位PE (悲观)": d['pe_20'],
                "50%分位PE (合理)": d['pe_50'],
                "80%分位PE (乐观)": d['pe_80'],
                "悲观收益率": f"{roi_20:.1f}%",
                "合理收益率": f"{roi_50:.1f}%",
                "乐观收益率": f"{roi_80:.1f}%",
            })
    
    df = pd.DataFrame(all_results)
    
    # 样式美化
    st.subheader(f"📊 {n_years}年后：不同PE估值水位下的纯收益率预测")
    st.table(df.style.applymap(lambda x: 'color: red' if '-' in str(x) else 'color: green', 
                               subset=['悲观收益率', '合理收益率', '乐观收益率']))

render_analysis()

# --- 6. 逻辑说明 ---
st.markdown(f"""
---
### 📖 算法模型校正说明
1. **收益率计算**：表格显示的是**扣除 100% 本金后的净利润率**。如果显示 `-5.0%`，代表不仅没赚，还亏损了 5%。
2. **20%分位 PE (悲观)**：如果 {n_years} 年后市场依然极度低迷，估值仅修复到历史最差的 20% 水平。
3. **50%分位 PE (合理)**：回归到过去 10 年的平均估值水平，这是“等雨来”策略的最核心预期。
4. **80%分位 PE (乐观)**：市场进入过热期，产生“戴维斯双击”后的增强收益。
5. **为什么有的指数悲观收益率是负的？**
   - 因为当前该指数的 **PE** 可能已经高于其历史 20% 分位点，如果未来 ROE 增长慢于 PE 的回归压力，就会亏损。
""")
