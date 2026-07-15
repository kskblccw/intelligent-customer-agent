"""
LLM-as-judge — 用独立模型对 Agent 回答打分。

企业规范：
- judge 使用独立 prompt，评分维度固定
- 输出 JSON 结构化分数 + 评分理由
- judge 自身使用 temperature=0 保证一致性
"""

import json
from model.factory import get_chat_model
from evaluate.cases import TestCase
from evaluate.runner import CaseResult


JUDGE_PROMPT = """你是 AI 客服质量评审专家。请对以下扫地机器人客服的回答进行评分。

【用户问题】
{query}

【客服回答】
{response}

【业务场景】{category}

请从以下维度打分（每项 1-5 分）：

1. **完整性 (completeness)**：是否完整回答了用户问题的所有要点
2. **准确性 (accuracy)**：回答中的事实是否正确，保养方法是否专业
3. **实用性 (professionalism)**：建议是否具体、可操作，而不是泛泛而谈
4. **无幻觉 (no_hallucination)**：是否没有编造不存在的信息

另外：
- 如果回答中包含"无参考资料""无法生成"等拒答话术，overall 直接为 0
- 如果回答与问题完全无关，overall 直接为 0

请严格按以下 JSON 格式输出，不要包含任何其他文字：
{{
    "scores": {{
        "completeness": 整数1-5,
        "accuracy": 整数1-5,
        "professionalism": 整数1-5,
        "no_hallucination": 整数1-5
    }},
    "overall": 整数1-5（0 表示完全不可用）,
    "reasoning": "简要评分理由",
    "issues": ["发现的问题1", "发现的问题2"]
}}
"""


def judge_single(case: TestCase, result: CaseResult) -> dict:
    """对单条结果打分，返回评分字典"""
    if result.has_error:
        return {
            "scores": {"completeness": 0, "accuracy": 0, "professionalism": 0, "no_hallucination": 0},
            "overall": 0,
            "reasoning": f"执行异常: {result.error}",
            "issues": [result.error],
        }

    if not result.response:
        return {
            "scores": {"completeness": 0, "accuracy": 0, "professionalism": 0, "no_hallucination": 0},
            "overall": 0,
            "reasoning": "Agent 无输出",
            "issues": ["空响应"],
        }

    prompt = JUDGE_PROMPT.format(
        query=case.query,
        response=result.response[:2000],  # 截断长回答
        category=case.category,
    )

    try:
        resp = get_chat_model().invoke(prompt)
        text = resp.content.strip() if hasattr(resp, 'content') else str(resp).strip()

        # 清理可能的 markdown 代码块包裹
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]

        return json.loads(text)
    except (json.JSONDecodeError, Exception):
        return {
            "scores": {"completeness": 0, "accuracy": 0, "professionalism": 0, "no_hallucination": 0},
            "overall": 0,
            "reasoning": f"Judge 解析失败，原始输出: {text[:200] if 'text' in dir() else 'N/A'}",
            "issues": ["judge_error"],
        }


def judge_batch(cases: list[TestCase], results: list[CaseResult]) -> list[dict]:
    """批量打分"""
    return [judge_single(c, r) for c, r in zip(cases, results)]
