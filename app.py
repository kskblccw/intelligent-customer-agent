import os
import time
import hashlib

import streamlit as st
from agent.react_agent import ReactAgent
from agent.tools.agent_tools import _get_rag
from rag.vector_store import VectorStoreService
from storage.conversation_store import (
    create_conversation, list_conversations, delete_conversation,
    update_conversation_title,
    save_message, load_messages, load_recent_messages,
)

# 启动时自动检测并加载知识库
if "kb_checked" not in st.session_state:
    with st.spinner("正在检查知识库..."):
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

    # 处理上一轮提交的文件（必须在 file_uploader 渲染之前，否则不能改 kb_uploader）
    pending = st.session_state.pop("pending_upload_path", None)
    if pending:
        vs = VectorStoreService()
        try:
            is_new = vs.add_single_file(os.path.abspath(pending))
            if is_new:
                st.session_state["kb_total_docs"] = vs.collection_count()
                _get_rag().refresh_corpus()  # 新增文档后重建 BM25 索引
                st.session_state["upload_feedback"] = ("success", f"文件 {os.path.basename(pending)} 入库成功")
            else:
                st.session_state["upload_feedback"] = ("warning", f"文件 {os.path.basename(pending)} 已存在于知识库中，跳过")
        except Exception as e:
            st.session_state["upload_feedback"] = ("error", f"入库失败: {str(e)}")
        st.rerun()

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
        # 把文件路径存到独立 key，下轮渲染时在 uploader 之前处理
        st.session_state["pending_upload_path"] = file_path
        st.rerun()

    st.divider()
    st.subheader("已加载文件列表")

    # 删除文件回调
    def _delete_file(fname: str):
        fpath = os.path.join("data", fname)
        # 先计算 MD5，再删文件
        target_md5 = None
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                target_md5 = hashlib.md5(f.read()).hexdigest()
            os.remove(fpath)
        # 从 md5.txt 中移除对应记录
        md5_path = "md5.txt"
        if target_md5 and os.path.exists(md5_path):
            with open(md5_path, "r", encoding="utf-8") as f:
                keep = [l for l in f if l.strip() != target_md5]
            with open(md5_path, "w", encoding="utf-8") as f:
                f.writelines(keep)
        # 更新文档计数
        vs = VectorStoreService()
        st.session_state["kb_total_docs"] = vs.collection_count()
        # 从 error 列表中移除
        errs = st.session_state.get("kb_error_files", [])
        if fname in errs:
            errs.remove(fname)
            st.session_state["kb_error_files"] = errs

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
                st.caption(f"📄 {fname}")
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
                    st.button(
                        "删除", key=f"del_err_{fname}",
                        on_click=_delete_file, args=(fname,),
                    )
    else:
        st.caption("暂无知识文件")

    # ── 会话管理 ──
    st.divider()
    st.subheader("对话记录")
    convs = list_conversations()
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
                st.session_state.pop("message", None)  # 触发重载
                st.rerun()
        with col2:
            if st.button("🗑", key=f"delconv_{cid}"):
                delete_conversation(cid)
                if cid == st.session_state.get("conv_id"):
                    new_convs = list_conversations()
                    if new_convs:
                        st.session_state["conv_id"] = new_convs[0]["id"]
                    else:
                        st.session_state.pop("conv_id", None)  # 删光了，不自动补
                    st.session_state.pop("message", None)
                st.rerun()
    if st.button("+ 新建会话", use_container_width=True):
        st.session_state["conv_id"] = create_conversation()
        st.session_state.pop("message", None)  # 触发重载
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


if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

# ── 会话管理 ──
if "conv_id" not in st.session_state:
    convs = list_conversations()
    if convs:
        st.session_state["conv_id"] = convs[0]["id"]

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
        st.session_state["conv_id"] = create_conversation()
        st.session_state["message"] = []

    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})
    save_message(st.session_state["conv_id"], "user", prompt)
    # 首条消息自动设标题：取前 10 字
    convs = list_conversations()
    current = next((c for c in convs if c["id"] == st.session_state["conv_id"]), None)
    if current and not current["title"]:
        title = prompt.strip()[:10]
        update_conversation_title(st.session_state["conv_id"], title)

    raw_text = ""
    ai_texts: list[str] = []      # AI 文本（原始，未转义）
    tool_htmls: list[str] = []    # 工具结果（已转义 HTML）
    with st.chat_message("assistant"):
        think_placeholder = st.empty()
        answer_placeholder = st.empty()
        with st.spinner("智能客服思考中..."):
            history = load_recent_messages(st.session_state["conv_id"], limit=30)
            for chunk in st.session_state["agent"].execute(prompt, history=history):
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


