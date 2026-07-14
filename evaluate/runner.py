"""
评测执行器 — 批量执行 Agent 测试用例，收集 tool trace 和响应。

企业规范：
- 每次执行独立 trace，互不污染
- 记录每条用例的执行时间
- 异常不中断整批评测
"""

import time
from dataclasses import dataclass, field
from evaluate.cases import TestCase

from agent.tools.middleware import set_trace_collector


@dataclass
class ToolTrace:
    tool: str
    args: dict
    success: bool
    error: str = ""
    attempts: int = 1


@dataclass
class CaseResult:
    case: TestCase
    response: str = ""
    tool_traces: list[ToolTrace] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    error: str = ""

    @property
    def called_tools(self) -> list[str]:
        return [t.tool for t in self.tool_traces]

    @property
    def tool_call_count(self) -> int:
        return len(self.tool_traces)

    @property
    def failed_tools(self) -> list[ToolTrace]:
        return [t for t in self.tool_traces if not t.success]

    @property
    def has_error(self) -> bool:
        return bool(self.error)


def run_single(agent, case: TestCase) -> CaseResult:
    """执行单个测试用例，返回完整结果"""
    traces: list[dict] = []
    set_trace_collector(traces)

    result = CaseResult(case=case)
    t0 = time.perf_counter()

    try:
        full_response = ""
        for chunk in agent.execute(case.query):
            if isinstance(chunk, dict):
                full_response += chunk.get("content", "") + "\n"
            else:
                full_response += str(chunk)
        result.response = full_response.strip()
    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)}"
    finally:
        set_trace_collector(None)

    result.elapsed_seconds = round(time.perf_counter() - t0, 2)
    result.tool_traces = [
        ToolTrace(**t) for t in traces
    ]
    return result


def run_batch(agent, cases: list[TestCase], progress_callback=None) -> list[CaseResult]:
    """批量执行，返回结果列表。progress_callback(i, total) 用于进度显示"""
    results: list[CaseResult] = []
    total = len(cases)
    for i, case in enumerate(cases):
        result = run_single(agent, case)
        results.append(result)
        if progress_callback:
            progress_callback(i + 1, total)
    return results
