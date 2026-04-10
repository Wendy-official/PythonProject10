import streamlit as st
import json
import os
import pandas as pd

# --- 1. 数据持久化逻辑 ---
DB_FILE = 'anime_community_db.json'


def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- 2. 核心算法：策略 B (分集独立统计) ---
def add_community_score(data, anime, ep, new_score):
    if anime not in data:
        data[anime] = {"综合评分": 0.0}

    ep_key = f"第{ep}集"
    if ep_key not in data[anime]:
        # 初始化：sum(总分), count(该集人数), avg(该集均分)
        data[anime][ep_key] = {"sum": 0.0, "count": 0, "avg": 0.0}

    # 更新单集数据
    data[anime][ep_key]["sum"] += new_score
    data[anime][ep_key]["count"] += 1
    data[anime][ep_key]["avg"] = round(data[anime][ep_key]["sum"] / data[anime][ep_key]["count"], 2)

    # 更新动画整部综合评分 (所有已评单集均分的平均值)
    all_ep_infos = [v for k, v in data[anime].items() if isinstance(v, dict)]
    if all_ep_infos:
        all_avgs = [info["avg"] for info in all_ep_infos]
        data[anime]["综合评分"] = round(sum(all_avgs) / len(all_avgs), 2)

    save_data(data)


# --- 3. 网页界面设计 ---
st.set_page_config(page_title="动画公评网", layout="wide")
st.title("🌐 动画多人公评系统 (策略 B)")

data = load_data()

# 侧边栏：管理面板
with st.sidebar:
    st.header("⚙️ 管理面板")

    # 添加新动画
    with st.expander("➕ 添加新动画"):
        new_anime = st.text_input("动画名称")
        if st.button("确认入库"):
            if new_anime and new_anime not in data:
                data[new_anime] = {"综合评分": 0.0}
                save_data(data)
                st.rerun()

    # 清除功能
    st.markdown("---")
    st.subheader("🗑️ 数据清理")
    if data:
        target_anime = st.selectbox("选择操作对象", list(data.keys()))
        if st.button("🔥 彻底删除该动画"):
            del data[target_anime]
            save_data(data)
            st.rerun()

# 主界面：标签页
tab1, tab2 = st.tabs(["⭐ 参与评分与详情", "🏆 全站口碑榜"])

with tab1:
    if not data:
        st.info("库里还没有动画，请在左侧添加。")
    else:
        anime_list = list(data.keys())
        selected_anime = st.selectbox("请选择要评价的动画", anime_list)

        st.divider()
        col_input, col_stats = st.columns([1, 1.5])

        with col_input:
            st.subheader("📝 我要评分")
            ep = st.number_input("集数", min_value=1, step=1)
            # 采用 0.5 步长的评分条，更符合二次元评分习惯
            score = st.select_slider("你的评分", options=[i / 2 for i in range(21)], value=8.5)

            if st.button("提交评分"):
                add_community_score(data, selected_anime, ep, score)
                st.toast(f"已记录评分：{score} 分", icon="✅")
                st.rerun()

        with col_stats:
            st.subheader(f"📊 《{selected_anime}》分集统计")

            # 显示综合评分大字报
            st.metric("大众平均分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")

            # 提取单集数据并整理
            ep_details = []
            for k, v in data[selected_anime].items():
                if isinstance(v, dict):  # 过滤掉非单集字典的键
                    ep_details.append({
                        "集数": int(k.replace("第", "").replace("集", "")),
                        "单集平均分": v["avg"],
                        "评价人数": v["count"]
                    })

            if ep_details:
                df_details = pd.DataFrame(ep_details).sort_values("集数")
                # 绘图
                st.line_chart(df_details.set_index("集数")["单集平均分"])
                # 展示表格 (使用列配置美化人数显示)
                st.dataframe(
                    df_details,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "评价人数": st.column_config.NumberColumn(format="%d 人")
                    }
                )

with tab2:
    st.subheader("🏆 全站战力排行")
    if data:
        leaderboard = []
        for name, info in data.items():
            # 计算全集累计评价人次，体现热度
            total_hits = sum([v['count'] for k, v in info.items() if isinstance(v, dict)])
            leaderboard.append({
                "动画名称": name,
                "大众综合分": info.get("综合评分", 0.0),
                "累计评价人次": total_hits
            })

        df_leader = pd.DataFrame(leaderboard).sort_values("大众综合分", ascending=False)
        st.dataframe(
            df_leader,
            use_container_width=True,
            hide_index=True,
            column_config={
                "大众综合分": st.column_config.NumberColumn(format="%.2f ⭐"),
                "累计评价人次": st.column_config.NumberColumn(format="%d 次")
            }
        )
    else:
        st.write("暂无数据")
from streamlit_javascript import st_javascript
import streamlit as st

# 获取浏览器标识
def get_browser_fingerprint():
    # 这段 JS 代码会返回浏览器的 UserAgent 字符串
    ua_info = st_javascript("navigator.userAgent")
    return ua_info

# 在你的网页中使用
st.subheader("🕵️ 浏览器标识检测")
browser_id = get_browser_fingerprint()

if browser_id:
    st.info(f"你的当前设备标识为: {browser_id}")
    # 你可以对这个长字符串进行哈希处理，生成一个简短的唯一 ID
    import hashlib
    short_id = hashlib.md5(browser_id.encode()).hexdigest()[:8]
    st.write(f"你的匿名身份 ID: {short_id}")
else:
    st.warning("正在获取浏览器标识...")



