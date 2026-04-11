import streamlit as st
import pandas as pd
import hashlib
import time
from supabase import create_client
from streamlit_javascript import st_javascript

# --- 1. 初始化数据库连接 ---
# 从 Streamlit Cloud 的 Secrets 获取云端地址和钥匙
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(url, key)
except Exception as e:
    st.error("❌ 数据库配置未找到！请在 Streamlit Settings -> Secrets 中配置 URL 和 KEY。")
    st.stop()

ADMIN_PASSWORD = "121023"  # 保持你设定的管理员密码


# --- 2. 云端数据读写逻辑 ---

def get_cloud_data():
    """从 Supabase 实时抓取并构建本地展示逻辑"""
    try:
        # 从数据库抓取所有评分记录
        response = supabase.table("anime_scores").select("*").execute()
        raw_data = response.data
        structured = {}

        # 将数据库的扁平化数据转回你的字典结构，方便代码逻辑复用
        for row in raw_data:
            name = row['anime_name']
            ep = f"第{row['episode']}集"
            uid = row['user_id']
            val = row['score']

            if name not in structured:
                structured[name] = {"综合评分": 0.0}
            if ep not in structured[name]:
                structured[name][ep] = {"voter_dict": {}}

            structured[name][ep]["voter_dict"][uid] = val

        # 实时计算平均分和统计信息
        for name in structured:
            all_ep_avgs = []
            for k, v in structured[name].items():
                if isinstance(v, dict) and "voter_dict" in v:
                    scores = list(v["voter_dict"].values())
                    avg = round(sum(scores) / len(scores), 2)
                    structured[name][k]["avg"] = avg
                    structured[name][k]["count"] = len(scores)
                    all_ep_avgs.append(avg)

            if all_ep_avgs:
                structured[name]["综合评分"] = round(sum(all_ep_avgs) / len(all_ep_avgs), 2)
        return structured
    except Exception as e:
        # 如果是新表没数据，返回空字典
        return {}


def save_score_to_cloud(anime, ep, score, uid):
    """保存评分到 Supabase。如果该用户对该集已评分，upsert 会自动执行更新"""
    data_to_save = {
        "anime_name": anime,
        "episode": ep,
        "user_id": uid,
        "score": score
    }
    # 使用 upsert 确保 (anime_name, episode, user_id) 组合是唯一的
    supabase.table("anime_scores").upsert(data_to_save, on_conflict="anime_name, episode, user_id").execute()


# --- 3. 获取浏览器指纹 ---
def get_user_id():
    ua = st_javascript("navigator.userAgent")
    if ua and ua != 0:
        return hashlib.md5(ua.encode()).hexdigest()[:8]
    return None


# --- 4. 网页界面 ---
st.set_page_config(page_title="群内四月番评分榜", layout="wide")
data = get_cloud_data()  # 每次刷新页面都从云端取最新数
uid = get_user_id()

st.title("🌐 群内四月番评分榜 ")

# --- 隐藏的侧边栏管理逻辑 ---
with st.sidebar:
    st.header("📌 频道信息")
    st.info("欢迎来到四月番评分社区！在这里你可以记录并分享你对每集动画的看法。")

    st.markdown("<br><br>" * 10, unsafe_allow_html=True)
    enable_admin = st.checkbox("🔑", help="管理员入口")

    if enable_admin:
        st.divider()
        input_pwd = st.text_input("验证码", type="password")
        if input_pwd == ADMIN_PASSWORD:
            st.success("管理权限已激活")
            # 数据库模式下，你可以直接在侧边栏删除动画（其实是删除该名称下的所有记录）
            if data:
                st.markdown("---")
                target_anime = st.selectbox("删除操作", list(data.keys()))
                if st.button("🔥 执行彻底删除"):
                    supabase.table("anime_scores").delete().eq("anime_name", target_anime).execute()
                    st.success(f"已从云端抹除 {target_anime}")
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
    # 数据库模式优化：如果库里没动画，允许输入，如果有，则下拉选择
    anime_options = list(data.keys())
    if not anime_options:
        selected_anime = st.text_input("库里还没动画，输入你要评分的第一个动画名：")
    else:
        # 这里加一个“+ 添加新动画”的选项在下拉列表里
        selected_anime = st.selectbox("选择动画", anime_options)

    if selected_anime:
        col_left, col_right = st.columns([1, 1.5])

        with col_left:
            st.subheader("📝 我要评分")
            ep = st.number_input("集数", min_value=1, step=1)

            # 实时从当前 data 中获取该用户的旧分
            current_ep_data = data.get(selected_anime, {}).get(f"第{ep}集", {})
            user_old_score = current_ep_data.get("voter_dict", {}).get(uid)

            if user_old_score is not None:
                st.info(f"💡 你的记录：你曾打过 **{user_old_score}** 分")
                default_val = float(user_old_score)
            else:
                st.caption("✨ 首次评价该集")
                default_val = 8.5

            score = st.select_slider("滑动评分", options=[i / 2 for i in range(21)], value=default_val)

            if st.button("提交 / 修改并同步到云端"):
                if uid:
                    # 直接调用云端保存函数
                    save_score_to_cloud(selected_anime, ep, score, uid)
                    if user_old_score is not None:
                        st.success(f"✅ 已更新：{user_old_score} ➡️ {score}")
                    else:
                        st.success(f"🎉 首次评价成功并存入云端！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("正在识别 ID，请稍等...")

        with col_right:
            if selected_anime in data:
                st.subheader(f"📊 《{selected_anime}》分集统计")
                st.metric("综合平均分", f"{data[selected_anime].get('综合评分', 0.0)} ⭐")
                rows = []
                for k, v in data[selected_anime].items():
                    if isinstance(v, dict) and "avg" in v:
                        rows.append({
                            "集数": int(k.replace("第", "").replace("集", "")),
                            "均分": v["avg"],
                            "人数": v.get("count", 0)
                        })
                if rows:
                    df = pd.DataFrame(rows).sort_values("集数")
                    st.line_chart(df.set_index("集数")["均分"])
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("该动画暂无云端评分数据。")

with tab2:
    st.subheader("🏆 全站排行榜")
    if data:
        lb_data = []
        for n, i in data.items():
            total_hits = sum([v.get('count', 0) for k, v in i.items() if isinstance(v, dict)])
            lb_data.append({
                "动画名称": n,
                "综合分": i.get("综合评分", 0.0),
                "总评价人次": total_hits
            })
        st.dataframe(pd.DataFrame(lb_data).sort_values("综合分", ascending=False), use_container_width=True,
                     hide_index=True)
