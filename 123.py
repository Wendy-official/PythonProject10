import streamlit as st
import json
import os
import pandas as pd
import hashlib
import time
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


# --- 3. 核心算法 ---
def add_or_update_score(data, anime, ep, new_score, user_id):
    if anime not in data:
        data[anime] = {"综合评分": 0.0}
    ep_key = f"第{ep}集"
    if ep_key not in data[anime]:
        data[anime][ep_key] = {"avg": 0.0, "voter_dict": {}}
    voter_dict = data[anime][ep_key].get("voter_dict", {})
    old_score = voter_dict.get(user_id)
    is_update = user_id in voter_dict
    voter_dict[user_id] = new_score
    data[anime][ep_key]["voter_dict"] = voter_dict
    all_scores = list(voter_dict.values())
    data[anime][ep_key]["count"] = len(all_scores)
    data[anime][ep_key]["avg"] = round(sum(all_scores) / len(all_scores), 2)
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

# --- 隐藏的侧边栏管理逻辑 ---
with st.sidebar:
    st.header("📌 频道信息")
    st.info("欢迎来到动画公评社区！在这里你可以记录并分享你对每集动画的看法。")

    # 在侧边栏最底部设置一个极其隐蔽的“开发者入口”
    st.markdown("<br><br>" * 10, unsafe_allow_html=True)  # 用空格把入口推到最下面
    enable_admin = st.checkbox("🔑", help="管理员入口")  # 只用一个 Emoji 做开关

    if enable_admin:
        st.divider()
        input_pwd = st.text_input("验证码", type="password")
        if input_pwd == ADMIN_PASSWORD:
            st.success("管理权限已激活")
            with st.expander("➕ 添加新动画"):
                new_name = st.text_input("动画名称")
                if st.button("确认入库"):
                    if new_name and new_name not in data:
                        data[new_name] = {"综合评分": 0.0};
                        save_data(data);
                        st.rerun()

            if data:
                st.markdown("---")
                target_anime = st.selectbox("删除操作", list(data.keys()))
                if st.button("🔥 执行彻底删除"):
                    del data[target_anime];
                    save_data(data);
                    st.rerun()
        elif input_pwd:
            st.error("密钥无效")

# 主界面显示
if uid:
    st.caption(f"您的匿名身份 ID: `{uid}`")
else:
    st.caption("正在识别设备标识...")

tab1, tab2 = st.tabs(["⭐ 评分详情", "🏆 战力排行"])

with tab1:
    if not data:
        st.info("暂无数据，请等待管理员初始化库。")
    else:
        selected_anime = st.selectbox("选择要评价的动画", list(data.keys()))
        col_left, col_right = st.columns([1, 1.5])

        with col_left:
            st.subheader("📝 我要评分")
            ep = st.number_input("集数", min_value=1, step=1)
            current_ep_data = data[selected_anime].get(f"第{ep}集", {})
            user_old_score = current_ep_data.get("voter_dict", {}).get(uid)

            if user_old_score is not None:
                st.info(f"💡 你的记录：你曾打过 **{user_old_score}** 分")
                default_val = float(user_old_score)
            else:
                st.caption("✨ 首次评价该集")
                default_val = 8.5

            score = st.select_slider("滑动评分", options=[i / 2 for i in range(21)], value=default_val)

            if st.button("提交 / 修改评分"):
                if uid:
                    is_update, old_val = add_or_update_score(data, selected_anime, ep, score, uid)
                    if is_update:
                        st.success(f"✅ 已更新：{old_val} ➡️ {score}")
                    else:
                        st.success(f"🎉 首次评价成功！")
                    time.sleep(1);
                    st.rerun()

        with col_right:
            st.subheader(f"📊 《{selected_anime}》分集统计")
            st.metric("综合平均分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")
            rows = []
            for k, v in data[selected_anime].items():
                if isinstance(v, dict):
                    rows.append({"集数": int(k.replace("第", "").replace("集", "")), "均分": v["avg"],
                                 "人数": v.get("count", 0)})
            if rows:
                df = pd.DataFrame(rows).sort_values("集数")
                st.line_chart(df.set_index("集数")["均分"])
                st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("🏆 全站排行榜")
    if data:
        lb_data = [{"动画名称": n, "综合分": i.get("综合评分", 0.0),
                    "总人次": sum([v.get('count', 0) for k, v in i.items() if isinstance(v, dict)])} for n, i in
                   data.items()]
        st.dataframe(pd.DataFrame(lb_data).sort_values("综合分", ascending=False), use_container_width=True,
                     hide_index=True)
