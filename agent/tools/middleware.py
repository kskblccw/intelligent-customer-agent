#中间件开发
import time
import random
from typing import Callable

from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from utils.logger_handler import logger
from utils.prompt_loader import load_report_prompts,load_system_prompts

MAX_RETRIES = 3       # 最多重试 3 次（总共 4 次尝试）
BASE_DELAY = 1.0      # 基础等待秒数


@wrap_tool_call
def monitor_tool(request:ToolCallRequest,handler:Callable[[ToolCallRequest],ToolMessage | Command]) -> ToolMessage | Command:
    tool_name = request.tool_call['name']
    logger.info(f"[monitor_tool]执行工具：{tool_name}")
    logger.info(f"[monitor_tool]传入参数：{request.tool_call['args']}")

    last_exception = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = handler(request)
            if attempt > 0:
                logger.info(f"[monitor_tool]工具{tool_name}在第{attempt}次重试后成功")
            else:
                logger.info(f"[monitor_tool]执行工具：{tool_name}调用成功")
            if tool_name == "fill_context_for_report":
                request.runtime.context['report'] = True
            return result

        except Exception as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    f"[monitor_tool]工具{tool_name}第{attempt+1}次调用失败，"
                    f"{delay:.1f}秒后重试(剩余{MAX_RETRIES - attempt}次)：{str(e)}"
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"[monitor_tool]工具{tool_name}重试{MAX_RETRIES}次后仍失败，"
                    f"原因：{str(e)}"
                )

    raise last_exception  # type: ignore[misc]


@before_model
def log_before_model(
        state:AgentState,#整个agent智能体中的状态记录
        runtime:Runtime, #记录了整个执行过程中的上下文信息
):   #在模型执行前输出日志
    logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息")
    logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content.strip()}")
    return None

@dynamic_prompt   #每一次在生成提示词之前，调用此函数
def report_prompt_switch(request:ModelRequest):  #动态切换提示词
    is_report = request.runtime.context.get("report", False)
    if is_report:   #说明调用了报告总结的工具，我们需要切换提示词
        return load_report_prompts()

    return load_system_prompts()
