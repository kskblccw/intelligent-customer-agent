from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import rag_search,get_weather,get_user_location,get_user_id,get_current_month,fetch_external_data,fill_context_for_report
from agent.tools.middleware import monitor_tool,log_before_model,report_prompt_switch

MAX_HISTORY_MESSAGES = 20
SUMMARY_EVERY_N = 10  # 超出窗口时，每 10 条旧消息压缩为一条摘要

_SUMMARIZE_PROMPT = SystemMessage(content=(
    "你是对话摘要助手。用一段简短的中文概括以下对话的关键信息，"
    "包括：用户身份、偏好、核心诉求、已做出的决策、待办事项。不超过150字。"
))

def _compact_history(history: list[dict]) -> list[dict]:
    """将超出窗口的旧消息用 LLM 压缩为一条摘要，保留最近的消息"""
    if len(history) <= MAX_HISTORY_MESSAGES:
        return list(history)

    overflow = history[:-MAX_HISTORY_MESSAGES]
    recent = history[-MAX_HISTORY_MESSAGES:]

    # 每 SUMMARY_EVERY_N 条为一批，逐批摘要
    summaries: list[str] = []
    for i in range(0, len(overflow), SUMMARY_EVERY_N):
        batch = overflow[i:i + SUMMARY_EVERY_N]
        batch_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '客服'}: {m['content']}"
            for m in batch
        )
        resp = chat_model.invoke([_SUMMARIZE_PROMPT, HumanMessage(content=batch_text)])
        content = resp.content.strip() if hasattr(resp, 'content') else str(resp).strip()
        if content:
            summaries.append(content)

    summary = " | ".join(summaries) if summaries else "（无关键信息）"
    return [
        {"role": "user", "content": f"[历史对话摘要] {summary}"}
    ] + recent


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_search,get_weather,get_user_location,get_user_id,get_current_month,fetch_external_data,fill_context_for_report],
            middleware=[ monitor_tool,log_before_model,report_prompt_switch]
        )

    def execute(self, query: str, history: list[dict] | None = None):
        messages = _compact_history(history) if history else []
        messages.append({"role": "user", "content": query})

        input_dict = {"messages": messages}
        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            latest = chunk["messages"][-1]
            if not latest.content:
                continue
            text = str(latest.content).strip()
            if not text:
                continue
            if isinstance(latest, AIMessage):
                yield {"type": "ai", "content": text}
            elif isinstance(latest, ToolMessage):
                yield {"type": "tool", "content": text}
            else:
                yield {"type": "ai", "content": text}




if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute("给我生成一份我的使用报告信息"):
        print(chunk,end="",flush=True)