import streamlit as st
import json
import os
import pandas as pd
import hashlib
import time
from streamlit_javascript import st_javascript

# --- 1. 配置与数据持久化 ---
DB_FILE = 'anime_community_db.json'
ADMIN_PASSWORD = "你的私密密码"  # 请修改为您自己的密码


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


# --- 2. 获取浏览器指纹 (匿名 ID) ---
def get_user_id():
    ua = st_javascript("navigator.userAgent")
    if ua and ua != 0:
        return hashlib.md5(ua.encode()).hexdigest()[:8]
    return None


# --- 3. 核心算法：支持修改历史分的逻辑 ---
def add_or_update_score(data, anime, ep, new_score, user_id):
    if anime not in data:
        data[anime] = {"综合评分": 0.0}

    ep_key = f"第{ep}集"
    if ep_key not in data[anime]:
        data[anime][ep_key] = {"avg": 0.0, "voter_dict": {}}

    voter_dict = data[anime][ep_key].get("voter_dict", {})

    # 在更新前记录旧分数，用于反馈显示
    old_score = voter_dict.get(user_id)
    is_update = user_id in voter_dict

    # 执行更新
    voter_dict[user_id] = new_score
    data[anime][ep_key]["voter_dict"] = voter_dict

    # 重新计算该集平均分和总人数
    all_scores = list(voter_dict.values())
    data[anime][ep_key]["count"] = len(all_scores)
    data[anime][ep_key]["avg"] = round(sum(all_scores) / len(all_scores), 2)

    # 更新整部动画综合分 (已评单集的平均分之和 / 已评集数)
    all_ep_infos = [v for k, v in data[anime].items() if isinstance(v, dict)]
    if all_ep_infos:
        all_avgs = [info["avg"] for info in all_ep_infos]
        data[anime]["综合评分"] = round(sum(all_avgs) / len(all_avgs), 2)

    save_data(data)
    return is_update, old_score


# --- 4. 网页界面 ---
st.set_page_config(page_title="动画公评网", layout="wide")
data = load_data()
uid = get_user_id()

st.title("🌐 动画多人公评系统")

# 侧边栏：管理面板
with st.sidebar:
    st.header("⚙️ 管理面板")
    input_pwd = st.text_input("管理员密码", type="password")

    if input_pwd == ADMIN_PASSWORD:
        st.success("管理员已解锁")
        with st.expander("➕ 添加新动画", expanded=True):
            new_name = st.text_input("动画名称")
            if st.button("确认入库"):
                if new_name and new_name not in data:
                    data[new_name] = {"综合评分": 0.0}
                    save_data(data)
                    st.rerun()

        st.markdown("---")
        if data:
            target_anime = st.selectbox("选择要删除的动画", list(data.keys()))
            if st.button("🔥 彻底删除"):
                del data[target_anime]
                save_data(data)
                st.rerun()
    elif input_pwd:
        st.error("密码错误")

# 主界面显示 ID
if uid:
    st.caption(f"您的匿名身份 ID: `{uid}`")
else:
    st.caption("正在识别设备标识...")

tab1, tab2 = st.tabs(["⭐ 评分详情", "🏆 战力排行"])

with tab1:
    if not data:
        st.info("库中暂无动画，请联系管理员。")
    else:
        selected_anime = st.selectbox("选择要评价的动画", list(data.keys()))
        col_left, col_right = st.columns([1, 1.5])

        with col_left:
            st.subheader("📝 我要评分")
            ep = st.number_input("集数", min_value=1, step=1)

            # 预读取旧分数
            current_ep_data = data[selected_anime].get(f"第{ep}集", {})
            user_old_score = current_ep_data.get("voter_dict", {}).get(uid)

            if user_old_score is not None:
                st.info(f"💡 你的记录：此次第 {ep} 集评分为 **{user_old_score}** 分")
                default_val = float(user_old_score)
            else:
                st.caption("✨ 这是你对此集的首次评价")
                default_val = 8.5

            score = st.select_slider("滑动评分", options=[i / 2 for i in range(21)], value=default_val)

            if st.button("提交 / 修改评分"):
                if uid:
                    is_update, old_val = add_or_update_score(data, selected_anime, ep, score, uid)
                    if is_update:
                        st.success(f"✅ 修改成功！分数已从 {old_val} 变更为 {score}")
                    else:
                        st.success(f"🎉 首次评价成功：{score} 分")

                    time.sleep(1)  # 停留1秒让用户看清反馈
                    st.rerun()
                else:
                    st.warning("设备标识未就绪，请稍等或刷新页面")

        with col_right:
            st.subheader(f"📊 《{selected_anime}》分集统计")
            st.metric("综合平均分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")

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
    st.subheader("🏆 全站口碑排行榜")
    if data:
        lb_data = []
        for name, info in data.items():
            total_hits = sum([v.get('count', 0) for k, v in info.items() if isinstance(v, dict)])
            lb_data.append({
                "动画名称": name,
                "综合评分": info.get("综合评分", 0.0),
                "累计评价人次": total_hits
            })

        df_lb = pd.DataFrame(lb_data).sort_values("综合评分", ascending=False)
        st.dataframe(df_lb, use_container_width=True, hide_index=True)
