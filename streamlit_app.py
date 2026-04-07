"""
智能投顾助手 - Streamlit 应用
使用 AkShare 获取实时市场数据
"""

import time

import pandas as pd
import streamlit as st

from market_data_real import get_market_data

# 页面配置
st.set_page_config(
    page_title="智能投顾助手 - 市场概览",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.5rem;
    }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .positive {
        color: #ff4d4f;
    }
    .negative {
        color: #52c41a;
    }
    </style>
""", unsafe_allow_html=True)


def display_index_group(group_name, indices_data, icon):
    """显示一组指数数据"""
    st.markdown(f"### {icon} {group_name}")

    # 创建列布局，每行显示4个指标
    cols = st.columns(4)

    for i, idx in enumerate(indices_data):
        col = cols[i % 4]

        with col:
            # Streamlit 的 inverse: 上涨红色、下跌绿色
            delta_color = "off" if idx['change_pct'] == 0 else "inverse"

            # 显示指标卡片
            st.metric(
                label=idx['name'],
                value=f"{idx['price']:.2f}",
                delta=f"{idx['change_pct']:+.2f}% ({idx['change_amount']:+.2f})",
                delta_color=delta_color
            )

    st.markdown("---")


def main():
    """主函数"""

    # 标题
    st.markdown('<h1 class="main-title">📊 智能投顾助手 - 市场概览</h1>', unsafe_allow_html=True)

    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 控制面板")

        # 自动刷新开关
        auto_refresh = st.checkbox("🔄 自动刷新", value=True)

        # 刷新间隔
        refresh_interval = st.slider("刷新间隔（秒）", min_value=5, max_value=60, value=10)

        # 手动刷新按钮
        if st.button("🔄 立即刷新"):
            st.rerun()

        st.markdown("---")
        st.info("""
        💡 **使用说明**

        • 红色表示上涨
        • 绿色表示下跌
        • 数据来源：AkShare
        • 点击刷新按钮获取最新数据
        """)

    # 加载数据
    with st.spinner("正在获取市场数据..."):
        try:
            market_data = get_market_data()

            # 检查是否成功获取数据
            if not market_data or (
                not market_data['a_stock'] and
                not market_data['hk_us'] and
                not market_data['bond_commodity']
            ):
                st.error("❌ 未能获取到市场数据，请稍后重试")
                return

        except Exception as e:
            st.error(f"❌ 数据获取失败: {str(e)}")
            st.exception(e)
            return

    # 显示最后更新时间
    current_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"🕐 最后更新时间: {current_time}")

    # ============= A股/港美/债商 三分组 =============
    if market_data['a_stock']:
        display_index_group("A股", market_data['a_stock'], "🇨🇳")

    if market_data['hk_us']:
        display_index_group("港美", market_data['hk_us'], "🌏")

    if market_data['bond_commodity']:
        display_index_group("债/商", market_data['bond_commodity'], "💰")

    # ============= 数据表格视图 =============
    with st.expander("📋 查看详细数据表格"):
        st.subheader("A股详情")

        # A股表格
        a_stock_df = pd.DataFrame(market_data['a_stock'])
        if not a_stock_df.empty:
            # 添加颜色样式
            def color_negative_red(val):
                color = '#ff4d4f' if val > 0 else '#52c41a' if val < 0 else 'black'
                return f'color: {color}'

            styled_df = a_stock_df.style.applymap(color_negative_red, subset=['change_pct', 'change_amount'])
            st.dataframe(styled_df, use_container_width=True)

        # 港美表格
        st.subheader("港美详情")
        hk_us_df = pd.DataFrame(market_data['hk_us'])
        if not hk_us_df.empty:
            styled_df = hk_us_df.style.applymap(color_negative_red, subset=['change_pct', 'change_amount'])
            st.dataframe(styled_df, use_container_width=True)

        st.subheader("债/商详情")
        bond_df = pd.DataFrame(market_data['bond_commodity'])
        if not bond_df.empty:
            styled_df = bond_df.style.applymap(color_negative_red, subset=['change_pct', 'change_amount'])
            st.dataframe(styled_df, use_container_width=True)

    # 自动刷新逻辑
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
