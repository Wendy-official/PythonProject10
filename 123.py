import streamlit as st
import json
import os
import pandas as pd

DB_FILE = 'anime_community_db.json'


# --- 增强型数据处理 ---
def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- 核心逻辑：多人评分算法 ---
def add_community_score(data, anime, ep, new_score):
    if anime not in data:
        data[anime] = {"综合评分": 0.0, "总评价人数": 0}

    ep_key = f"第{ep}集"
    if ep_key not in data[anime]:
        # 初始化单集统计
        data[anime][ep_key] = {"sum": 0.0, "count": 0, "avg": 0.0}

    # 累加分数和人数
    data[anime][ep_key]["sum"] += new_score
    data[anime][ep_key]["count"] += 1
    data[anime][ep_key]["avg"] = round(data[anime][ep_key]["sum"] / data[anime][ep_key]["count"], 2)

    # 更新整部动画的综合数据
    all_ep_avgs = [info["avg"] for k, info in data[anime].items() if isinstance(info, dict)]
    data[anime]["综合评分"] = round(sum(all_ep_avgs) / len(all_ep_avgs), 2)
    data[anime]["总评价人数"] = sum([info["count"] for k, info in data[anime].items() if isinstance(info, dict)])

    save_data(data)


# --- 网页界面 ---
st.set_page_config(page_title="动画公评网", layout="wide")
st.title("🌐 动画多人公评系统")

data = load_data()

# 侧边栏：管理与入库
with st.sidebar:
    st.header("⚙️ 管理面板")
    new_anime = st.text_input("添加新动画到公库")
    if st.button("确认入库"):
        if new_anime and new_anime not in data:
            data[new_anime] = {"综合评分": 0.0, "总评价人数": 0}
            save_data(data)
            st.rerun()

# 主界面
tab1, tab2 = st.tabs(["📊 参与评分", "🏆 全站排行榜"])

with tab1:
    if not data:
        st.info("库中暂无动画，请先添加。")
    else:
        anime_list = list(data.keys())
        selected_anime = st.selectbox("选择你想要评价的动画", anime_list)

        st.divider()
        col_input, col_stats = st.columns([1, 1.5])

        with col_input:
            st.subheader("我要评分")
            ep = st.number_input("集数", min_value=1, step=1)
            score = st.select_slider("你的评分", options=[i / 2 for i in range(21)], value=8.0)

            if st.button("提交我的评分"):
                add_community_score(data, selected_anime, ep, score)
                st.balloons()
                st.success(f"提交成功！你是第 {data[selected_anime][f'第{ep}集']['count']} 个给这一集打分的人。")
                st.rerun()

        with col_stats:
            st.subheader(f"《{selected_anime}》全站统计")
            c1, c2 = st.columns(2)
            c1.metric("大众平均分", f"{data[selected_anime]['综合评分']} ⭐")
            c2.metric("累计参与人数", f"{data[selected_anime]['总评价人数']} 人")

            # 整理单集明细表
            ep_details = []
            for k, v in data[selected_anime].items():
                if isinstance(v, dict):
                    ep_details.append({"集数": k, "平均分": v["avg"], "评价人数": v["count"]})

            if ep_details:
                df_details = pd.DataFrame(ep_details).sort_values("集数")
                st.dataframe(df_details, use_container_width=True, hide_index=True)
                # 走势图
                st.line_chart(df_details.set_index("集数")["平均分"])

with tab2:
    st.subheader("全站口碑榜（按大众评分排序）")
    if data:
        leaderboard = []
        for name, info in data.items():
            leaderboard.append({
                "动画名称": name,
                "大众平均分": info["综合评分"],
                "参与评价总人次": info["总评价人数"]
            })
        df_leader = pd.DataFrame(leaderboard).sort_values("大众平均分", ascending=False)
        st.table(df_leader)



