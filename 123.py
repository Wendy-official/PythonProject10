import streamlit as st
import json
import os
import pandas as pd
import hashlib
from streamlit_javascript import st_javascript

# --- 1. 数据持久化 ---
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


# --- 2. 获取浏览器唯一标识 ---
def get_user_id():
    # 获取浏览器的 UserAgent（包含浏览器版本、系统等信息）
    ua = st_javascript("navigator.userAgent")
    if ua and ua != 0:
        # 使用 MD5 加密生成一个 8 位的唯一字符串
        return hashlib.md5(ua.encode()).hexdigest()[:8]
    return None


# --- 3. 核心算法：防刷分策略 B ---
def add_community_score(data, anime, ep, new_score, user_id):
    if anime not in data:
        data[anime] = {"综合评分": 0.0}

    ep_key = f"第{ep}集"
    if ep_key not in data[anime]:
        # 新增 voters 列表来记录投过分的用户 ID
        data[anime][ep_key] = {"sum": 0.0, "count": 0, "avg": 0.0, "voters": []}

    # 检查该用户是否评过这一集
    if user_id in data[anime][ep_key].get("voters", []):
        return False, "你已经评过这一集了，请勿重复提交哦！"

    # 更新数据
    data[anime][ep_key]["sum"] += new_score
    data[anime][ep_key]["count"] += 1
    if "voters" not in data[anime][ep_key]: data[anime][ep_key]["voters"] = []
    data[anime][ep_key]["voters"].append(user_id)
    data[anime][ep_key]["avg"] = round(data[anime][ep_key]["sum"] / data[anime][ep_key]["count"], 2)

    # 计算综合分
    all_ep_infos = [v for k, v in data[anime].items() if isinstance(v, dict)]
    if all_ep_infos:
        all_avgs = [info["avg"] for info in all_ep_infos]
        data[anime]["综合评分"] = round(sum(all_avgs) / len(all_avgs), 2)

    save_data(data)
    return True, "评分成功！"


# --- 4. 网页界面 ---
st.set_page_config(page_title="动画公评网", layout="wide")
data = load_data()

# 获取用户 ID
uid = get_user_id()

st.title("🌐 动画多人公评系统")
if uid:
    st.caption(f"您的匿名身份 ID: `{uid}` (基于浏览器标识)")
else:
    st.caption("正在识别您的设备标识...")

# 侧边栏
with st.sidebar:
    st.header("⚙️ 管理面板")
    with st.expander("➕ 添加新动画"):
        new_name = st.text_input("动画名称")
        if st.button("确认入库"):
            if new_name and new_name not in data:
                data[new_name] = {"综合评分": 0.0}
                save_data(data);
                st.rerun()

# 主界面
tab1, tab2 = st.tabs(["⭐ 参与评分", "🏆 战力排行榜"])

with tab1:
    if not data:
        st.info("请先添加动画")
    else:
        selected_anime = st.selectbox("选择动画", list(data.keys()))
        col_in, col_st = st.columns([1, 1.5])

        with col_in:
            st.subheader("📝 我要评分")
            ep = st.number_input("集数", min_value=1, step=1)
            score = st.select_slider("评分", options=[i / 2 for i in range(21)], value=8.5)

            if st.button("提交评分"):
                if not uid:
                    st.error("未能识别设备，请刷新页面重试")
                else:
                    success, msg = add_community_score(data, selected_anime, ep, score, uid)
                    if success:
                        st.success(msg);
                        st.rerun()
                    else:
                        st.error(msg)

        with col_st:
            st.subheader(f"📊 《{selected_anime}》统计")
            st.metric("大众评分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")

            # 数据表格
            ep_list = []
            for k, v in data[selected_anime].items():
                if isinstance(v, dict):
                    ep_list.append(
                        {"集数": int(k.replace("第", "").replace("集", "")), "均分": v["avg"], "人数": v["count"]})

            if ep_list:
                df = pd.DataFrame(ep_list).sort_values("集数")
                st.line_chart(df.set_index("集数")["均分"])
                st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("🏆 全站排行榜")
    if data:
        lb = [
            {"动画": n, "均分": i["综合评分"], "总人次": sum([v['count'] for k, v in i.items() if isinstance(v, dict)])}
            for n, i in data.items()]
        st.dataframe(pd.DataFrame(lb).sort_values("均分", ascending=False), use_container_width=True, hide_index=True)


