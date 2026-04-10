import streamlit as st
import json
import os
import pandas as pd
import hashlib
from streamlit_javascript import st_javascript

# --- 1. 配置与数据持久化 ---
DB_FILE = 'anime_community_db.json'
ADMIN_PASSWORD = "你的私密密码"


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


# --- 2. 获取浏览器指纹 ---
def get_user_id():
    ua = st_javascript("navigator.userAgent")
    if ua and ua != 0:
        return hashlib.md5(ua.encode()).hexdigest()[:8]
    return None


# --- 3. 核心算法：支持修改的评分逻辑 ---
def add_or_update_score(data, anime, ep, new_score, user_id):
    if anime not in data:
        data[anime] = {"综合评分": 0.0}

    ep_key = f"第{ep}集"
    if ep_key not in data[anime]:
        data[anime][ep_key] = {"avg": 0.0, "voter_dict": {}}  # 使用字典存储 {ID: 分数}

    # 兼容旧版本数据结构（如果之前有旧数据）
    if "voter_dict" not in data[anime][ep_key]:
        data[anime][ep_key]["voter_dict"] = {}
        # 如果有旧的 sum 和 count，这里无法回溯 ID，建议清理旧 JSON 重新开始

    # 获取该用户之前的分数（如果有）
    voter_dict = data[anime][ep_key]["voter_dict"]
    is_update = user_id in voter_dict

    # 更新该用户的分数
    voter_dict[user_id] = new_score

    # 重新计算该集数据
    all_scores = list(voter_dict.values())
    data[anime][ep_key]["count"] = len(all_scores)
    data[anime][ep_key]["avg"] = round(sum(all_scores) / len(all_scores), 2)

    # 更新整部动画综合分
    all_ep_infos = [v for k, v in data[anime].items() if isinstance(v, dict)]
    if all_ep_infos:
        all_avgs = [info["avg"] for info in all_ep_infos]
        data[anime]["综合评分"] = round(sum(all_avgs) / len(all_avgs), 2)

    save_data(data)
    return is_update


# --- 4. 网页界面 ---
st.set_page_config(page_title="动画公评网", layout="wide")
data = load_data()
uid = get_user_id()

st.title("🌐 动画多人公评系统")

# 侧边栏
with st.sidebar:
    st.header("⚙️ 管理面板")
    input_pwd = st.text_input("管理员密码", type="password")
    if input_pwd == ADMIN_PASSWORD:
        st.success("管理员已解锁")
        with st.expander("➕ 添加新动画"):
            new_name = st.text_input("名称")
            if st.button("入库"):
                if new_name and new_name not in data:
                    data[new_name] = {"综合评分": 0.0};
                    save_data(data);
                    st.rerun()
        if data:
            target = st.selectbox("选择要删除的动画", list(data.keys()))
            if st.button("🔥 彻底删除"):
                del data[target];
                save_data(data);
                st.rerun()

# 主界面
if uid:
    st.caption(f"您的设备匿名 ID: `{uid}`")
else:
    st.caption("正在识别设备标识...")

tab1, tab2 = st.tabs(["⭐ 评分详情", "🏆 战力排行"])

with tab1:
    if not data:
        st.info("暂无数据")
    else:
        selected_anime = st.selectbox("选择动画", list(data.keys()))
        col_left, col_right = st.columns([1, 1.5])

        with col_left:
            st.subheader("📝 我要评分")
            ep = st.number_input("集数", min_value=1, step=1)

            # 自动检测用户是否已评分，给出当前分数提示
            current_ep_data = data[selected_anime].get(f"第{ep}集", {})
            user_old_score = current_ep_data.get("voter_dict", {}).get(uid)

            if user_old_score is not None:
                st.info(f"提示：你此前给第 {ep} 集打了 {user_old_score} 分。再次提交将覆盖原分数。")
                default_score = user_old_score
            else:
                default_score = 8.5

            score = st.select_slider("评分", options=[i / 2 for i in range(21)], value=float(default_score))

            if st.button("确认提交/修改"):
                if uid:
                    is_update = add_or_update_score(data, selected_anime, ep, score, uid)
                    if is_update:
                        st.success(f"已更新第 {ep} 集的评分为 {score}")
                    else:
                        st.success(f"第 {ep} 集首次评分成功！")
                    st.rerun()

        with col_right:
            st.subheader(f"📊 《{selected_anime}》分集统计")
            st.metric("大众均分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")

            rows = []
            for k, v in data[selected_anime].items():
                if isinstance(v, dict):
                    rows.append({
                        "集数": int(k.replace("第", "").replace("集", "")),
                        "平均分": v["avg"],
                        "人数": v.get("count", 0)
                    })
            if rows:
                df = pd.DataFrame(rows).sort_values("集数")
                st.line_chart(df.set_index("集数")["平均分"])
                st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("🏆 全站排行榜")
    if data:
        lb = [{"动画": n, "综合分": i["综合评分"],
               "总人次": sum([v.get('count', 0) for k, v in i.items() if isinstance(v, dict)])} for n, i in
              data.items()]
        st.dataframe(pd.DataFrame(lb).sort_values("综合分", ascending=False), use_container_width=True, hide_index=True)

