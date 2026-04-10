import streamlit as st
import json
import os
import pandas as pd
import hashlib
from streamlit_javascript import st_javascript

# --- 1. 配置与数据持久化 ---
DB_FILE = 'anime_community_db.json'
# 建议上线后在 Streamlit Cloud 的 Secrets 中设置，或者直接改这里的字符串
ADMIN_PASSWORD = "123456"


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


# --- 2. 获取浏览器指纹 (防刷分关键) ---
def get_user_id():
    # 获取浏览器的 UserAgent 信息
    ua = st_javascript("navigator.userAgent")
    if ua and ua != 0:
        # 生成 8 位唯一匿名 ID
        return hashlib.md5(ua.encode()).hexdigest()[:8]
    return None


# --- 3. 核心算法：带 ID 校验的评分逻辑 ---
def add_community_score(data, anime, ep, new_score, user_id):
    if anime not in data:
        data[anime] = {"综合评分": 0.0}

    ep_key = f"第{ep}集"
    if ep_key not in data[anime]:
        data[anime][ep_key] = {"sum": 0.0, "count": 0, "avg": 0.0, "voters": []}

    # 防刷分检查
    current_voters = data[anime][ep_key].get("voters", [])
    if user_id in current_voters:
        return False, f"你的 ID({user_id}) 已经评过这一集了，请勿重复刷分。"

    # 更新单集数据
    data[anime][ep_key]["sum"] += new_score
    data[anime][ep_key]["count"] += 1
    data[anime][ep_key]["voters"] = current_voters + [user_id]
    data[anime][ep_key]["avg"] = round(data[anime][ep_key]["sum"] / data[anime][ep_key]["count"], 2)

    # 更新整部动画综合分
    all_ep_infos = [v for k, v in data[anime].items() if isinstance(v, dict)]
    if all_ep_infos:
        all_avgs = [info["avg"] for info in all_ep_infos]
        data[anime]["综合评分"] = round(sum(all_avgs) / len(all_avgs), 2)

    save_data(data)
    return True, "评分提交成功！"


# --- 4. 网页界面 ---
st.set_page_config(page_title="动画公评网", layout="wide")
data = load_data()
uid = get_user_id()

st.title("🌐 动画多人公评系统")

# 侧边栏：管理权限锁
with st.sidebar:
    st.header("⚙️ 管理面板")
    input_pwd = st.text_input("管理员密码", type="password")

    if input_pwd == ADMIN_PASSWORD:
        st.success("权限已解锁")
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
        st.error("密码不正确")
    else:
        st.info("请输入管理员密码以进行库管理")

# 主界面：展示与评分
if uid:
    st.caption(f"您的设备匿名 ID: `{uid}`")
else:
    st.caption("正在识别设备标识，请稍候...")

tab1, tab2 = st.tabs(["⭐ 评分详情", "🏆 战力排行"])

with tab1:
    if not data:
        st.info("库中暂无动画，请联系管理员添加。")
    else:
        selected_anime = st.selectbox("选择要评价的动画", list(data.keys()))
        col_left, col_right = st.columns([1, 1.5])

        with col_left:
            st.subheader("📝 提交我的分数")
            ep = st.number_input("集数", min_value=1, step=1)
            score = st.select_slider("评分", options=[i / 2 for i in range(21)], value=8.5)

            if st.button("确认提交"):
                if uid:
                    success, msg = add_community_score(data, selected_anime, ep, score, uid)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("正在获取浏览器标识，请稍后再试一次")

        with col_right:
            st.subheader(f"📊 《{selected_anime}》分集统计")
            st.metric("大众均分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")

            # 整理数据
            rows = []
            for k, v in data[selected_anime].items():
                if isinstance(v, dict):
                    rows.append({
                        "集数": int(k.replace("第", "").replace("集", "")),
                        "平均分": v["avg"],
                        "人数": v["count"]
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
            total_voters = sum([v['count'] for k, v in info.items() if isinstance(v, dict)])
            lb_data.append({
                "动画名称": name,
                "综合评分": info.get("综合评分", 0.0),
                "累计评价人次": total_voters
            })

        df_lb = pd.DataFrame(lb_data).sort_values("综合评分", ascending=False)
        st.dataframe(df_lb, use_container_width=True, hide_index=True)

