import os
import time
import hashlib

import streamlit as st
from agent.react_agent import ReactAgent
from rag.vector_store import VectorStoreService

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

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    st.session_state["message"] = []

for message in st.session_state["message"]:
    st.chat_message(message['role']).write(message['content'])


#用户输入提示词
prompt = st.chat_input()


if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role":"user","content":prompt})

    response_messages = []
    with st.spinner("智能客服思考中..."):
       res_stream =  st.session_state["agent"].execute(prompt, history=st.session_state["message"])

       def capture(generator,cache_list):
           for chunk in generator:
               cache_list.append(chunk)

               for char in chunk:
                   time.sleep(0.01)
                   yield char

       st.chat_message("assistant").write_stream(capture(res_stream,response_messages))
       st.session_state["message"].append({"role":"assistant","content":response_messages[-1]})
       st.rerun()


