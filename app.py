import os
import time
import hashlib
import threading

import streamlit as st
from agent.react_agent import ReactAgent
from agent.tools.agent_tools import _get_rag
from rag.vector_store import VectorStoreService
from storage.conversation_store import (
    create_conversation, list_conversations, delete_conversation,
    update_conversation_title,
    save_message, load_messages, load_recent_messages,
    register_user, verify_user, reset_password,
    create_session, validate_session, delete_session,
)
from utils.config_handler import agent_config
import urllib.request, json

# ── 城市定位 ──
GAODE_KEY = os.environ.get("GAODE_KEY", "") or agent_config.get("gaodekey", "")
DEFAULT_CITY = agent_config.get("default_city", "广州市")


def _generate_conversation_title(conv_id: str, prompt: str, user_id: str):
    """后台线程：用 LLM 生成对话摘要标题，失败时退回前 10 字"""
    try:
        from model.factory import get_chat_model
        llm = get_chat_model()
        title = llm.invoke(
            f"将以下用户问题概括为一个简洁的标题（不超过15字），只返回标题文本，不要任何标点或解释：\n{prompt.strip()}"
        ).content.strip()
        if len(title) > 20:
            title = title[:20]
        update_conversation_title(conv_id, title, user_id)
    except Exception:
        update_conversation_title(conv_id, prompt.strip()[:10], user_id)


def _ip_to_city(ip: str) -> str | None:
    try:
        url = f"https://restapi.amap.com/v3/ip?key={GAODE_KEY}&ip={ip}"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") != "1":
            return None
        city = data.get("city", "")
        province = data.get("province", "")
        if isinstance(city, list):
            city = "".join(city)
        if isinstance(province, list):
            province = "".join(province)
        return str(city).strip() or str(province).strip() or None
    except Exception:
        return None


def _get_client_ip() -> str | None:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx is None:
            return None
        session = ctx.session
        for attr in ("_ws", "ws", "_websocket_handler"):
            ws = getattr(session, attr, None)
            if ws and hasattr(ws, "request"):
                return ws.request.remote_ip
        for name in dir(session):
            if "ws" in name.lower() or "socket" in name.lower():
                obj = getattr(session, name, None)
                if obj is None:
                    continue
                if hasattr(obj, "request"):
                    return obj.request.remote_ip
                if hasattr(obj, "remote_address"):
                    addr = obj.remote_address
                    return addr[0] if isinstance(addr, tuple) else addr
        return None
    except Exception:
        return None


# Resolve city once per session
if "user_city" not in st.session_state:
    city = None
    client_ip = _get_client_ip()
    if client_ip:
        city = _ip_to_city(client_ip)
    st.session_state["user_city"] = city or DEFAULT_CITY
    st.session_state["city_source"] = "IP定位" if city else "默认"

# ── 刷新后自动恢复登录态 ──
if "user_id" not in st.session_state:
    token = st.query_params.get("session_token")
    if token:
        session = validate_session(token)
        if session:
            st.session_state["user_id"] = session["user_id"]
            st.session_state["username"] = session["username"]

# ── 登录 / 注册 ──
if "user_id" not in st.session_state:
    st.markdown("""
    <style>
        .stApp { background: #060D1A; }
        header[data-testid="stHeader"] { display: none; }
        [data-testid="stToolbar"] { display: none; }
        section[data-testid="stSidebar"] { display: none; }
        .stMain > div { padding: 0 !important; max-width: none !important; }
        [data-testid="stHorizontalBlock"] { gap: 0 !important; flex-wrap: nowrap !important; }

        /* ==== 右栏毛玻璃卡片 ==== */
        [data-testid="stVerticalBlockBorderWrapper"] {
            max-width: 54% !important; min-width: 320px !important;
            margin: 0 auto !important;
            padding: 28px 32px 20px !important;
            background: rgba(12,25,50,0.75) !important;
            backdrop-filter: blur(20px) !important; -webkit-backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(59,130,246,0.12) !important;
            border-radius: 16px !important;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important;
        }
        .auth-input input {
            border-radius: 8px !important;
            border: 1px solid transparent !important; background: #1a2438 !important;
            font-size: 14px !important; color: #E2E8F0 !important;
            padding: 8px 12px !important; transition: border-color 0.2s !important;
        }
        .auth-input input::placeholder { color: #64748B !important; }
        .auth-input input:hover { border-color: rgba(59,130,246,0.3) !important; }
        .auth-input input:focus { border-color: #3b82f6 !important; box-shadow: none !important; }
        .auth-btn button {
            height: 40px !important; border-radius: 8px !important;
            background: linear-gradient(135deg, #163270, #254fb8) !important;
            border: none !important; color: #FFF !important;
            font-size: 14px !important; font-weight: 600 !important;
            cursor: pointer !important; transition: all 0.2s !important;
        }
        .auth-btn button:hover {
            background: linear-gradient(135deg, #1a3e8a, #3060d0) !important;
            transform: translateY(-1px);
        }
        .auth-link-btn button {
            background: transparent !important; border: none !important;
            color: #94A3B8 !important; font-size: 13px !important;
            font-weight: 400 !important; padding: 2px 0 !important;
            height: auto !important; transition: all 0.15s !important;
        }
        .auth-link-btn button:hover {
            color: #60a5fa !important;
            text-decoration: underline !important;
            text-underline-offset: 4px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1], gap="small")

    with left_col:
        st.markdown("""
        <div style="background:linear-gradient(160deg,#0A1629 0%,#132347 40%,#1A3366 100%);
            min-height:100vh; display:flex; align-items:center; justify-content:center;
            padding:80px 64px; position:relative; overflow:hidden;">
        <div style="position:absolute;top:-200px;right:-200px;width:600px;height:600px;
            border-radius:50%;background:radial-gradient(circle,rgba(22,93,255,0.15) 0%,transparent 70%);"></div>
        <div style="position:absolute;bottom:-100px;left:-100px;width:400px;height:400px;
            border-radius:50%;background:radial-gradient(circle,rgba(22,93,255,0.08) 0%,transparent 70%);"></div>
        <div style="position:relative;z-index:1;max-width:440px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:56px;">
            <div style="width:36px;height:36px;border-radius:8px;background:#165DFF;
            color:#FFF;font-size:1.1rem;font-weight:700;line-height:36px;text-align:center;">S</div>
            <span style="color:#FFF;font-size:18px;font-weight:600;">SmartService</span>
        </div>
        <h1 style="font-size:36px;font-weight:700;color:#FFF;margin:0 0 16px;
            letter-spacing:-0.03em;line-height:1.25;">智能维保<br>客服平台</h1>
        <p style="font-size:16px;color:rgba(255,255,255,0.55);margin:0 0 48px;line-height:1.6;">
            企业级智能扫地机器人售后服务系统，融合 RAG 检索与 ReAct Agent，提供专业高效的客户服务体验。</p>
        <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:28px;">
            <div style="width:32px;height:32px;border-radius:8px;background:#E8F0FE;
            display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;">🤖</div>
            <div><div style="font-size:15px;color:#FFF;font-weight:600;margin-bottom:4px;">AI 智能客服</div>
            <div style="font-size:13px;color:rgba(255,255,255,0.4);">LangGraph ReAct Agent 多工具协作</div></div>
        </div>
        <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:28px;">
            <div style="width:32px;height:32px;border-radius:8px;background:#FEF3C7;
            display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;">📚</div>
            <div><div style="font-size:15px;color:#FFF;font-weight:600;margin-bottom:4px;">RAG 知识检索</div>
            <div style="font-size:13px;color:rgba(255,255,255,0.4);">BM25 + 向量混合检索精准定位</div></div>
        </div>
        <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:28px;">
            <div style="width:32px;height:32px;border-radius:8px;background:#D1FAE5;
            display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;">📊</div>
            <div><div style="font-size:15px;color:#FFF;font-weight:600;margin-bottom:4px;">企业级评测</div>
            <div style="font-size:13px;color:rgba(255,255,255,0.4);">30 条用例 × LLM-as-judge</div></div>
        </div>
        </div></div>
        """, unsafe_allow_html=True)

    with right_col:
        st.markdown('<div style="margin-top:18vh"></div>', unsafe_allow_html=True)

        page = st.session_state.get("auth_page", "login")
        titles = {"login": "欢迎回来", "register": "创建账号", "forgot": "重置密码"}
        subtitles = {
            "login": "登录您的账号以继续使用",
            "register": "注册后即可使用智能维保客服系统",
            "forgot": "输入用户名和新密码完成重置",
        }
        btn_labels = {"login": "登  录", "register": "注  册", "forgot": "重置密码"}

        with st.container(border=True):
            st.markdown(f"""
            <h2 style="font-size:22px;font-weight:700;color:#F1F5F9;margin:0 0 4px;">{titles[page]}</h2>
            <p style="font-size:13px;color:#94A3B8;margin:0 0 20px;">{subtitles[page]}</p>
            """, unsafe_allow_html=True)

            with st.form("auth_form", clear_on_submit=False):
                st.markdown('<div class="auth-input">', unsafe_allow_html=True)
                username = st.text_input("用户名", placeholder="请输入用户名", label_visibility="collapsed")
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

                st.markdown('<div class="auth-input">', unsafe_allow_html=True)
                if page == "forgot":
                    password = st.text_input("新密码", type="password", placeholder="新密码（至少4位）", label_visibility="collapsed")
                else:
                    password = st.text_input("密码", type="password", placeholder="请输入密码", label_visibility="collapsed")
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
                st.markdown('<div class="auth-btn">', unsafe_allow_html=True)
                submitted = st.form_submit_button(btn_labels[page], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                if submitted:
                    if not username.strip() or not password:
                        st.error("请填写完整信息")
                    elif page == "register":
                        if len(password) < 4:
                            st.error("密码长度不能少于4位")
                        else:
                            uid = register_user(username.strip(), password)
                            if uid:
                                st.session_state["user_id"] = uid
                                st.session_state["username"] = username.strip()
                                st.session_state.pop("auth_page", None)
                                st.session_state["login_toast"] = True
                                token = create_session(uid, username.strip())
                                st.query_params["session_token"] = token
                                st.rerun()
                            else:
                                st.error("用户名已存在")
                    elif page == "forgot":
                        if len(password) < 4:
                            st.error("新密码长度不能少于4位")
                        elif reset_password(username.strip(), password):
                            st.success("密码重置成功，请登录")
                            st.session_state["auth_page"] = "login"
                            st.rerun()
                        else:
                            st.error("用户名不存在")
                    else:
                        uid = verify_user(username.strip(), password)
                        if uid:
                            st.session_state["user_id"] = uid
                            st.session_state["username"] = username.strip()
                            st.session_state.pop("auth_page", None)
                            st.session_state["login_toast"] = True
                            token = create_session(uid, username.strip())
                            st.query_params["session_token"] = token
                            st.rerun()
                        else:
                            st.error("用户名或密码错误")

        # 底部链接（也在 container 内）
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

        def _switch_page(p):
            st.session_state["auth_page"] = p

        st.markdown('<div class="auth-link-btn">', unsafe_allow_html=True)
        if page == "login":
            c1, c2, c3 = st.columns([1, 0.3, 1])
            with c1:
                st.button("忘记密码？", key="go_forgot", use_container_width=True,
                          on_click=_switch_page, args=("forgot",))
            with c2:
                st.markdown('<div style="text-align:center;line-height:32px;color:rgba(148,163,184,0.4);">·</div>', unsafe_allow_html=True)
            with c3:
                st.button("注册新账号", key="go_register", use_container_width=True,
                          on_click=_switch_page, args=("register",))
        else:
            st.button("← 返回登录", key="go_login", use_container_width=True,
                      on_click=_switch_page, args=("login",))
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# ── 已登录 ──
user_id = st.session_state["user_id"]
username = st.session_state["username"]

# ── 处理耗时操作（带 loading 反馈）──
def _process_pending_actions():
    """统一处理需要 spinner 反馈的耗时操作：删除文件、删除会话、上传文件"""
    # 1. 删除知识文件
    pending_del_file = st.session_state.pop("pending_delete_file", None)
    if pending_del_file:
        fname = pending_del_file
        with st.spinner(f"正在删除文件 {fname}..."):
            fpath = os.path.join("data", fname)
            target_md5 = None
            abs_path = os.path.abspath(fpath)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    target_md5 = hashlib.md5(f.read()).hexdigest()
                os.remove(fpath)
            md5_path = "md5.txt"
            if target_md5 and os.path.exists(md5_path):
                with open(md5_path, "r", encoding="utf-8") as f:
                    keep = [l for l in f if l.strip() != target_md5]
                with open(md5_path, "w", encoding="utf-8") as f:
                    f.writelines(keep)
            vs = VectorStoreService()
            vs.delete_by_source(abs_path)
            st.session_state["kb_total_docs"] = vs.collection_count()
            _get_rag().refresh_corpus()
            errs = st.session_state.get("kb_error_files", [])
            if fname in errs:
                errs.remove(fname)
                st.session_state["kb_error_files"] = errs
        st.toast(f"文件 {fname} 已删除", icon="🗑")
        st.rerun()

    # 2. 删除会话
    pending_del_conv = st.session_state.pop("pending_delete_conv", None)
    if pending_del_conv:
        cid, uid = pending_del_conv
        with st.spinner("正在删除对话记录..."):
            delete_conversation(cid, uid)
            if cid == st.session_state.get("conv_id"):
                new_convs = list_conversations(uid)
                if new_convs:
                    st.session_state["conv_id"] = new_convs[0]["id"]
                else:
                    st.session_state.pop("conv_id", None)
                st.session_state.pop("message", None)
        st.toast("对话记录已删除", icon="🗑")
        st.rerun()

    # 3. 上传知识文件入库
    pending_upload = st.session_state.pop("pending_upload_path", None)
    if pending_upload:
        basename = os.path.basename(pending_upload)
        with st.spinner(f"正在处理文件 {basename}..."):
            vs = VectorStoreService()
            try:
                is_new = vs.add_single_file(os.path.abspath(pending_upload))
                if is_new:
                    st.session_state["kb_total_docs"] = vs.collection_count()
                    _get_rag().refresh_corpus()
                    st.session_state["upload_feedback"] = ("success", f"文件 {basename} 入库成功")
                else:
                    st.session_state["upload_feedback"] = ("warning", f"文件 {basename} 已存在于知识库中，跳过")
            except Exception as e:
                st.session_state["upload_feedback"] = ("error", f"入库失败: {str(e)}")
        st.rerun()

_process_pending_actions()

if st.session_state.pop("login_toast", False):
    st.toast(f"欢迎回来，{username}！", icon="👋")

# 启动时自动检测并加载知识库
if "kb_checked" not in st.session_state:
    with st.spinner("正在加载系统知识库，首次可能需 1-2 分钟，请稍候..."):
        vs = VectorStoreService()
        doc_count = vs.collection_count()
        if doc_count == 0:
            with st.spinner("知识库为空，正在自动加载知识文件..."):
                stats = vs.load_document()
                st.session_state["kb_startup_loaded"] = stats.get("loaded", [])
                st.session_state["kb_startup_errors"] = stats.get("errors", [])
            st.rerun()
        else:
            stats = vs.load_document()
            st.session_state["kb_startup_loaded"] = stats.get("loaded", [])
            st.session_state["kb_startup_errors"] = stats.get("errors", [])
        st.session_state["kb_total_docs"] = vs.collection_count()
        st.session_state["kb_checked"] = True
        # 如果启动时新加载了文件，刷新 RAG 的 BM25 语料
        if st.session_state.get("kb_startup_loaded"):
            _get_rag().refresh_corpus()

# 启动时一次性 toast
startup_loaded = st.session_state.pop("kb_startup_loaded", [])
startup_errors = st.session_state.pop("kb_startup_errors", [])
if startup_loaded:
    st.toast(f"已加载 {len(startup_loaded)} 个新知识文件")
if startup_errors:
    st.toast(f"{len(startup_errors)} 个文件加载失败，可在侧边栏查看并删除", icon="⚠️")
    st.session_state["kb_error_files"] = startup_errors

#标题
st.title("智能扫地机器人维保客服")
st.divider()

with st.sidebar:
    st.subheader("城市设置")
    city_source = st.session_state.get("city_source", "默认")
    st.caption(f"当前城市（{city_source}）")

    def _on_city_change():
        st.session_state["user_city"] = st.session_state["_city_selector"]
        st.session_state["city_source"] = "手动选择"

    city_options = [
        "广州市", "深圳市", "北京市", "上海市", "杭州市",
        "成都市", "武汉市", "南京市", "重庆市", "西安市",
        "长沙市", "苏州市", "天津市", "郑州市", "东莞市",
    ]
    current_city = st.session_state.get("user_city", DEFAULT_CITY)
    if current_city not in city_options:
        city_options.insert(0, current_city)
    try:
        idx = city_options.index(current_city)
    except ValueError:
        idx = 0

    st.selectbox(
        "选择城市",
        city_options,
        index=idx,
        key="_city_selector",
        on_change=_on_city_change,
        label_visibility="collapsed",
    )
    st.divider()

    st.subheader("知识库状态")
    st.metric("文档块总数", st.session_state.get("kb_total_docs", "—"))

    # 上传反馈（一次性消费）
    upload_feedback = st.session_state.pop("upload_feedback", None)
    if upload_feedback:
        level, msg = upload_feedback
        if level == "success":
            st.success(msg)
        elif level == "warning":
            st.warning(msg)
        elif level == "error":
            st.error(msg)

    st.divider()
    st.subheader("上传知识文件")

    uploaded = st.file_uploader(
        "支持 TXT / PDF",
        type=["txt", "pdf"],
        key="kb_uploader",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, uploaded.name)
        with open(file_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state["pending_upload_path"] = file_path
        st.rerun()

    st.divider()
    st.subheader("已加载文件列表")

    data_dir = "data"
    if os.path.isdir(data_dir):
        md5_path = "md5.txt"
        loaded_md5s = set()
        if os.path.exists(md5_path):
            with open(md5_path, "r", encoding="utf-8") as f:
                loaded_md5s = {line.strip() for line in f if line.strip()}
        kb_files = [f for f in os.listdir(data_dir) if f.endswith((".txt", ".pdf"))]
        loaded_files = []
        for fname in sorted(kb_files):
            fpath = os.path.join(data_dir, fname)
            if not os.path.isfile(fpath):
                continue
            with open(fpath, "rb") as f:
                md5 = hashlib.md5(f.read()).hexdigest()
            if md5 in loaded_md5s:
                loaded_files.append(fname)
        if loaded_files:
            for fname in loaded_files:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"📄 {fname}")
                with col2:
                    if st.button("删除", key=f"del_loaded_{fname}"):
                        st.session_state["pending_delete_file"] = fname
                        st.rerun()
        else:
            st.caption("暂无知识文件")

        # 异常文件：加载失败的，提供删除入口
        error_files = st.session_state.get("kb_error_files", [])
        if error_files:
            st.divider()
            st.subheader("加载失败的文件")
            st.caption("以下文件无法解析，建议删除后重新上传正确版本")
            for fname in error_files:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"❌ {fname}")
                with col2:
                    if st.button("删除", key=f"del_err_{fname}"):
                        st.session_state["pending_delete_file"] = fname
                        st.rerun()
    else:
        st.caption("暂无知识文件")

    # ── 会话管理 ──
    st.divider()
    st.subheader("对话记录")
    convs = list_conversations(user_id)
    for c in convs:
        cid = c["id"]
        label = c["title"] or cid
        active = cid == st.session_state.get("conv_id", "")
        prefix = "● " if active else "○ "
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(prefix + label, key=f"conv_{cid}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state["conv_id"] = cid
                st.session_state.pop("message", None)
                st.rerun()
        with col2:
            if st.button("🗑", key=f"delconv_{cid}"):
                st.session_state["pending_delete_conv"] = (cid, user_id)
                st.rerun()
    if st.button("+ 新建会话", use_container_width=True):
        st.session_state["conv_id"] = create_conversation(user_id)
        st.session_state.pop("message", None)
        st.rerun()

    # 登出
    st.divider()
    if st.button("🚪 退出登录", use_container_width=True):
        token = st.query_params.get("session_token")
        if token:
            delete_session(token)
        for k in ("user_id", "username", "conv_id", "message", "agent"):
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()

def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _build_thinking_html(ai_chunks: list[str], tool_chunks: list[str], *, open_panel: bool = False) -> str:
    """构建思考过程 HTML：早期 AI + 工具结果。open_panel=True 时默认展开"""
    parts: list[str] = []
    for ai in ai_chunks:
        parts.append(f"<div style='white-space:pre-wrap; line-height:1.5; margin:2px 0;'>{_escape(ai)}</div>")
    parts.extend(tool_chunks)
    if not parts:
        return ""
    tag = "<details open>" if open_panel else "<details>"
    return (
        f"{tag}"
        "<summary style='font-size:0.85em; color:#999; cursor:pointer;'>思考过程</summary>"
        f"<div style='padding:4px 0;'>{''.join(parts)}</div>"
        "</details>"
    )

def _char_generator(text: str, delay: float = 0.015):
    """逐字 yield，模拟打字效果"""
    for ch in text:
        yield ch
        time.sleep(delay)


@st.cache_resource
def _get_agent():
    return ReactAgent()


if "agent" not in st.session_state:
    st.session_state["agent"] = _get_agent()

# ── 会话管理 ──
if "message" not in st.session_state:
    if "conv_id" in st.session_state:
        try:
            rows = load_messages(st.session_state["conv_id"])
            st.session_state["message"] = [
                {"role": r["role"], "content": r["content"],
                 "answer": r.get("answer"), "thinking_html": r.get("thinking_html")}
                for r in rows
            ]
        except Exception:
            st.session_state["message"] = []
    else:
        st.session_state["message"] = []

for message in st.session_state["message"]:
    if message["role"] == "assistant":
        thinking_html = message.get("thinking_html", "")
        answer = _escape(message.get("answer", message["content"]))
        if thinking_html:
            html = thinking_html + f"<div style='white-space:pre-wrap; line-height:1.6; margin-top:8px;'>{answer}</div>"
        else:
            html = f"<div style='white-space:pre-wrap; line-height:1.6;'>{answer}</div>"
        st.chat_message("assistant").markdown(html, unsafe_allow_html=True)
    else:
        st.chat_message(message["role"]).write(message["content"])


#用户输入提示词
prompt = st.chat_input()


if prompt:
    # 没有会话时自动创建（删光后的首次发言）
    if "conv_id" not in st.session_state:
        st.session_state["conv_id"] = create_conversation(user_id)
        st.session_state["message"] = []

    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})
    save_message(st.session_state["conv_id"], "user", prompt)
    # 首条消息自动设标题：LLM 摘要
    convs = list_conversations(user_id)
    current = next((c for c in convs if c["id"] == st.session_state["conv_id"]), None)
    if current and not current["title"]:
        threading.Thread(
            target=_generate_conversation_title,
            args=(st.session_state["conv_id"], prompt, user_id),
            daemon=True,
        ).start()

    raw_text = ""
    ai_texts: list[str] = []      # AI 文本（原始，未转义）
    tool_htmls: list[str] = []    # 工具结果（已转义 HTML）
    with st.chat_message("assistant"):
        think_placeholder = st.empty()
        answer_placeholder = st.empty()
        with st.spinner("智能客服思考中..."):
            history = load_recent_messages(st.session_state["conv_id"], limit=30)
            for chunk in st.session_state["agent"].execute(
                prompt, history=history,
                user_city=st.session_state.get("user_city", DEFAULT_CITY),
                user_id=user_id,
            ):
                if not isinstance(chunk, dict):
                    raw_text += str(chunk).strip() + "\n"
                    tool_htmls.append(
                        f"<div style='font-size:0.75em; color:#c66; font-family:monospace;'>"
                        f"[非预期 {type(chunk).__name__}] {_escape(str(chunk)[:200])}</div>"
                    )
                    continue

                text = chunk["content"].strip()
                if not text:
                    continue
                raw_text += text + "\n"
                safe = _escape(text)

                if chunk["type"] == "tool":
                    if len(text) > 200:
                        display = _escape(text[:200]) + (
                            f"<br><span style='color:#aaa;'>"
                            f"（已获取参考资料，共 {len(text)} 字）</span>"
                        )
                    else:
                        display = safe
                    tool_htmls.append(
                        f"<div style='font-size:0.75em; color:#999; font-family:monospace; "
                        f"margin:2px 0; padding:2px 6px; border-left:2px solid #ddd;'>{display}</div>"
                    )
                else:
                    ai_texts.append(text)

                # 思考面板：历史 AI + 全部工具结果（block 更新）
                prev_ai = ai_texts[:-1] if len(ai_texts) > 1 else []
                thinking_html = _build_thinking_html(prev_ai, tool_htmls)
                if thinking_html:
                    think_placeholder.markdown(thinking_html, unsafe_allow_html=True)
                else:
                    think_placeholder.empty()

                # 回答区域：最后一个 AI chunk，逐字流式
                if ai_texts:
                    answer_placeholder.write_stream(_char_generator(ai_texts[-1]))

    # 存储：思考 + 回答分开，历史记录能区分
    prev_ai = ai_texts[:-1] if len(ai_texts) > 1 else []
    thinking_html = _build_thinking_html(prev_ai, tool_htmls)
    answer_text = ai_texts[-1] if ai_texts else raw_text.strip()
    st.session_state["message"].append({
        "role": "assistant",
        "content": raw_text.strip(),
        "answer": answer_text,
        "thinking_html": thinking_html,
    })
    save_message(
        st.session_state["conv_id"], "assistant",
        content=raw_text.strip(),
        answer=answer_text,
        thinking_html=thinking_html,
    )
    # st.rerun()
