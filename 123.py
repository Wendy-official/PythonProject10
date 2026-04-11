import streamlit as st
import pandas as pd
import hashlib
import time
from supabase import create_client
from streamlit_javascript import st_javascript

# --- 1. 初始化数据库连接 ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(url, key)
except Exception as e:
    st.error("❌ 数据库连接配置有误，请检查 Secrets。")
    st.stop()

ADMIN_PASSWORD = "121023"


# --- 2. 云端数据读写逻辑 (已修复评分逻辑) ---
def get_cloud_data():
    try:
        response = supabase.table("anime_scores").select("*").execute()
        raw_data = response.data
        structured = {}

        for row in raw_data:
            name = row['anime_name']
            ep = f"第{row['episode']}集"
            uid = row['user_id']
            val = row['score']

            # 【关键修复】：计算评分时，完全无视系统占位符
            if uid == "SYSTEM":
                if name not in structured:
                    structured[name] = {"综合评分": 0.0}
                continue  # 跳过，不把 0 分计入 voter_dict

            if name not in structured:
                structured[name] = {"综合评分": 0.0}
            if ep not in structured[name]:
                structured[name][ep] = {"voter_dict": {}}

            structured[name][ep]["voter_dict"][uid] = val

        # 重新计算平均分
        for name in structured:
            all_ep_avgs = []
            for k, v in structured[name].items():
                if isinstance(v, dict) and "voter_dict" in v:
                    scores = list(v["voter_dict"].values())
                    if scores:  # 确保有分才算
                        avg = round(sum(scores) / len(scores), 2)
                        structured[name][k]["avg"] = avg
                        structured[name][k]["count"] = len(scores)
                        all_ep_avgs.append(avg)

            if all_ep_avgs:
                structured[name]["综合评分"] = round(sum(all_ep_avgs) / len(all_ep_avgs), 2)
        return structured
    except:
        return {}


def save_score_to_cloud(anime, ep, score, uid):
    data_to_save = {"anime_name": anime, "episode": ep, "user_id": uid, "score": score}
    supabase.table("anime_scores").upsert(data_to_save, on_conflict="anime_name, episode, user_id").execute()


# --- 3. 获取浏览器指纹 ---
def get_user_id():
    ua = st_javascript("navigator.userAgent")
    if ua and ua != 0:
        return hashlib.md5(ua.encode()).hexdigest()[:8]
    return None


# --- 4. 网页界面 ---
st.set_page_config(page_title="群内四月番评分榜", layout="wide")
data = get_cloud_data()
uid = get_user_id()

st.title("🌐 群内四月番评分榜")

# --- 🔐 侧边栏管理面板 ---
with st.sidebar:
    st.header("📌 频道信息")
    st.info("欢迎来到群内四月新番评分网络喵！请留下你对每集新番的评分～")

    st.markdown("<br><br>" * 10, unsafe_allow_html=True)
    enable_admin = st.checkbox("🔑", help="管理员入口")

    if enable_admin:
        st.divider()
        input_pwd = st.text_input("验证码", type="password")
        if input_pwd == ADMIN_PASSWORD:
            st.success("✅ 管理员权限已激活")

            with st.expander("➕ 添加新动画"):
                new_a = st.text_input("新动画全称")
                if st.button("确认入库"):
                    if new_a:
                        # 用集数 0 占位，确保不影响平均分
                        supabase.table("anime_scores").upsert(
                            {"anime_name": new_a, "episode": 0, "user_id": "SYSTEM", "score": 0.0},
                            on_conflict="anime_name, episode, user_id").execute()
                        st.success(f"《{new_a}》已入库！")
                        time.sleep(1);
                        st.rerun()

            if data:
                st.markdown("---")
                target = st.selectbox("选择要删除的动画", list(data.keys()))
                if st.button("🔥 执行彻底删除"):
                    supabase.table("anime_scores").delete().eq("anime_name", target).execute()
                    st.rerun()
        elif input_pwd:
            st.error("密钥无效")

# 主界面
if uid:
    st.caption(f"您的匿名身份 ID: `{uid}`")

tab1, tab2 = st.tabs(["⭐ 评分详情", "🏆 战力排行"])

with tab1:
    anime_list = sorted(list(data.keys()))
    if not anime_list:
        st.info("💡 暂无数据，请联系管理员添加。")
    else:
        selected_anime = st.selectbox("🎯 请选择动画", anime_list)
        col_l, col_r = st.columns([1, 1.5])

        with col_l:
            st.subheader("📝 我要评分")
            ep = st.number_input("集数", min_value=1, step=1)

            current_ep_data = data.get(selected_anime, {}).get(f"第{ep}集", {})
            user_old_score = current_ep_data.get("voter_dict", {}).get(uid)

            if user_old_score is not None:
                st.info(f"💡 你的记录：第 {ep} 集打过 **{user_old_score}** 分")
                default_val = float(user_old_score)
            else:
                st.caption("✨ 首次评价")
                default_val = 8.5

            score = st.select_slider("滑动评分", options=[i / 2 for i in range(21)], value=default_val)
            if st.button("提交 / 修改分数"):
                if uid:
                    save_score_to_cloud(selected_anime, ep, score, uid)
                    st.success("✅ 同步成功！")
                    time.sleep(1);
                    st.rerun()

        with col_r:
            st.subheader(f"📊 《{selected_anime}》统计")
            st.metric("综合平均分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")

            rows = []
            for k, v in data[selected_anime].items():
                if isinstance(v, dict) and "avg" in v:
                    ep_num = int(k.replace("第", "").replace("集", ""))
                    if ep_num > 0:
                        rows.append({"集数": ep_num, "均分": v["avg"], "人数": v.get("count", 0)})

            if rows:
                df = pd.DataFrame(rows).sort_values("集数")
                st.line_chart(df.set_index("集数")["均分"])
                st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("🏆 全站排行榜")
    if data:
        lb_data = []
        for n, i in data.items():
            total_hits = sum([v.get('count', 0) for k, v in i.items() if
                              isinstance(v, dict) and int(k.replace("第", "").replace("集", "")) > 0])
            lb_data.append({"动画名称": n, "综合分": i.get("综合评分", 0.0), "评价人次": total_hits})
        st.dataframe(pd.DataFrame(lb_data).sort_values("综合分", ascending=False), use_container_width=True,
                     hide_index=True)


