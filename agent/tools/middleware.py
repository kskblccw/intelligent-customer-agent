#中间件开发
from langchain.agents.middleware import wrap_tool_call

@wrap_tool_call
def monitor_tool():  #工具执行的监控
    pass


def log_before_model():   #在模型执行前输出日志
    pass


def report_prompt_switch():  #动态切换提示词
    pass