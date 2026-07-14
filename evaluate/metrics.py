"""
指标汇总 — 通过率统计、失败分类、基线对比。

企业规范：
- 按场景分类统计，不只是总体一个数字
- 失败原因细分到可操作的粒度
- 与基线对比，输出变化方向
"""

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from evaluate.cases import TestCase, CATEGORIES
from evaluate.runner import CaseResult


RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


@dataclass
class Summary:
    total: int = 0
    passed: int = 0
    avg_score: float = 0.0
    avg_tool_calls: float = 0.0
    avg_elapsed: float = 0.0
    by_category: dict[str, dict] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)
    failure_distribution: dict[str, int] = field(default_factory=dict)


def _classify_failure(case: TestCase, result: CaseResult, judge: dict) -> str:
    """对单条用例做失败根因分类"""
    if result.has_error:
        return "execution_error"
    if not result.response:
        return "empty_response"
    if judge.get("overall", 0) == 0:
        reasons = judge.get("issues", [])
        joined = " ".join(reasons).lower()
        if "无参考资料" in joined or "无法生成" in joined:
            return "rag_empty"
        if "无关" in joined:
            return "off_topic"
        return "judge_zero"
    if result.failed_tools:
        return "tool_failure"

    # 工具相关检查
    if case.expected_tools is not None:
        missing = set(case.expected_tools) - set(result.called_tools)
        if missing:
            return "missing_tool"

    if case.forbidden_tools:
        violated = set(case.forbidden_tools) & set(result.called_tools)
        if violated:
            return "wrong_tool"

    if case.max_tool_calls and result.tool_call_count > case.max_tool_calls:
        return "too_many_calls"

    if case.expected_keywords:
        missing_kw = [k for k in case.expected_keywords if k not in result.response]
        if missing_kw:
            return "missing_keyword"

    if case.forbidden_keywords:
        found_kw = [k for k in case.forbidden_keywords if k in result.response]
        if found_kw:
            return "forbidden_keyword"

    return "none"


def _check_pass(case: TestCase, result: CaseResult, judge: dict) -> bool:
    """判断单条用例是否通过"""
    if result.has_error:
        return False
    if judge.get("overall", 0) < 3:
        return False
    if result.failed_tools:
        return False
    if case.expected_tools is not None:
        if not set(case.expected_tools).issubset(set(result.called_tools)):
            return False
    if case.forbidden_tools:
        if set(case.forbidden_tools) & set(result.called_tools):
            return False
    if case.max_tool_calls and result.tool_call_count > case.max_tool_calls:
        return False
    if case.min_tool_calls and result.tool_call_count < case.min_tool_calls:
        return False
    if case.expected_keywords:
        if not all(k in result.response for k in case.expected_keywords):
            return False
    if case.forbidden_keywords:
        if any(k in result.response for k in case.forbidden_keywords):
            return False
    return True


def compute_summary(cases: list[TestCase], results: list[CaseResult], judges: list[dict]) -> Summary:
    """从评测结果计算汇总指标"""
    s = Summary(total=len(cases))
    cat_stats: dict[str, dict] = {c: {"total": 0, "passed": 0, "avg_score": 0.0} for c in CATEGORIES}

    for case, result, judge in zip(cases, results, judges):
        passed = _check_pass(case, result, judge)
        failure = _classify_failure(case, result, judge) if not passed else "none"
        score = judge.get("overall", 0)

        if passed:
            s.passed += 1

        # 分类统计
        cat = case.category
        cat_stats[cat]["total"] += 1
        if passed:
            cat_stats[cat]["passed"] += 1
        cat_stats[cat]["avg_score"] += score

        if not passed:
            s.failures.append({
                "id": case.id,
                "category": case.category,
                "query": case.query,
                "failure": failure,
                "score": score,
                "called_tools": result.called_tools,
                "tool_count": result.tool_call_count,
            })
            s.failure_distribution[failure] = s.failure_distribution.get(failure, 0) + 1

    # 计算均值
    scores = [j.get("overall", 0) for j in judges]
    s.avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    s.avg_tool_calls = round(sum(r.tool_call_count for r in results) / len(results), 2) if results else 0
    s.avg_elapsed = round(sum(r.elapsed_seconds for r in results) / len(results), 2) if results else 0

    for cat in cat_stats:
        t = cat_stats[cat]["total"]
        cat_stats[cat]["avg_score"] = round(cat_stats[cat]["avg_score"] / t, 2) if t else 0
    s.by_category = cat_stats

    return s


def save_results(cases: list[TestCase], results: list[CaseResult], judges: list[dict], summary: Summary,
                 filename: str = "latest.csv"):
    """保存评测结果到 CSV"""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, filename)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "任务ID", "场景分类", "输入问题", "期望工具", "实际工具", "工具调用次数",
            "judge评分", "是否通过", "失败原因", "执行耗时(s)", "异常信息"
        ])
        for case, result, judge in zip(cases, results, judges):
            passed = _check_pass(case, result, judge)
            failure = _classify_failure(case, result, judge) if not passed else "-"
            writer.writerow([
                case.id, case.category, case.query,
                ",".join(case.expected_tools) if case.expected_tools else "-",
                ",".join(result.called_tools),
                result.tool_call_count,
                judge.get("overall", 0),
                "通过" if passed else "失败",
                failure,
                result.elapsed_seconds,
                result.error,
            ])

    return path


def load_baseline() -> Summary | None:
    """加载基线 CSV，转为 Summary 结构"""
    path = os.path.join(RESULTS_DIR, "baseline.csv")
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return None

    total = len(rows)
    passed = sum(1 for r in rows if r["是否通过"] == "通过")
    scores = [int(r["judge评分"]) for r in rows if r["judge评分"].isdigit()]
    instances = [int(r["工具调用次数"]) for r in rows if r["工具调用次数"].isdigit()]

    s = Summary(total=total, passed=passed)
    s.avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    s.avg_tool_calls = round(sum(instances) / len(instances), 2) if instances else 0

    cat_stats: dict[str, dict] = {}
    for r in rows:
        cat = r["场景分类"]
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "passed": 0, "avg_score": 0.0}
        cat_stats[cat]["total"] += 1
        if r["是否通过"] == "通过":
            cat_stats[cat]["passed"] += 1
        if r["judge评分"].isdigit():
            cat_stats[cat]["avg_score"] += int(r["judge评分"])

    for cat in cat_stats:
        t = cat_stats[cat]["total"]
        cat_stats[cat]["avg_score"] = round(cat_stats[cat]["avg_score"] / t, 2) if t else 0
    s.by_category = cat_stats

    # 失败分布
    for r in rows:
        if r["失败原因"] != "-":
            s.failure_distribution[r["失败原因"]] = s.failure_distribution.get(r["失败原因"], 0) + 1

    return s


def save_baseline(summary: Summary):
    """将 latest.csv 复制为 baseline.csv"""
    import shutil
    latest = os.path.join(RESULTS_DIR, "latest.csv")
    baseline = os.path.join(RESULTS_DIR, "baseline.csv")
    if os.path.exists(latest):
        shutil.copy2(latest, baseline)


def diff_baseline(current: Summary, baseline: Summary) -> str:
    """对比当前结果和基线，生成可读的差异报告"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"基线对比报告 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append("")

    pass_rate = current.passed / current.total * 100 if current.total else 0
    base_pass_rate = baseline.passed / baseline.total * 100 if baseline.total else 0
    delta_pass = pass_rate - base_pass_rate

    lines.append(f"通过率:  {pass_rate:.1f}%  (基线 {base_pass_rate:.1f}%)  {'↑' if delta_pass > 0 else '↓' if delta_pass < 0 else '='} {abs(delta_pass):.1f}%")
    lines.append(f"均分:    {current.avg_score}  (基线 {baseline.avg_score})  {'↑' if current.avg_score > baseline.avg_score else '↓' if current.avg_score < baseline.avg_score else '='} {abs(current.avg_score - baseline.avg_score):.1f}")
    lines.append(f"平均工具调用: {current.avg_tool_calls}  (基线 {baseline.avg_tool_calls})")
    lines.append(f"平均耗时: {current.avg_elapsed}s")
    lines.append("")

    lines.append("按场景分类:")
    for cat in sorted(current.by_category.keys()):
        c = current.by_category[cat]
        b = baseline.by_category.get(cat, {})
        cp = c["passed"] / c["total"] * 100 if c["total"] else 0
        bp = b.get("passed", 0) / b.get("total", 1) * 100 if b.get("total") else 0
        d = cp - bp
        arrow = "↑" if d > 0 else "↓" if d < 0 else "="
        lines.append(f"  {cat:8s}: {cp:.0f}% (基线 {bp:.0f}%) {arrow}{abs(d):.0f}%  均分 {c['avg_score']}")

    lines.append("")
    lines.append("失败原因分布:")
    all_failures = set(current.failure_distribution.keys()) | set(baseline.failure_distribution.keys())
    for failure in sorted(all_failures):
        cur = current.failure_distribution.get(failure, 0)
        base = baseline.failure_distribution.get(failure, 0)
        d = cur - base
        arrow = "↑" if d > 0 else "↓" if d < 0 else "="
        lines.append(f"  {failure:20s}: {cur:2d} (基线 {base:2d}) {arrow}{abs(d)}")

    return "\n".join(lines)
