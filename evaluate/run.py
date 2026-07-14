"""
一键运行评测入口: python -m evaluate.run [--baseline]

选项:
  --baseline    将本次结果设为基线
  --rag-only    仅评测 RAG 检索质量
"""

import sys
import os
import time

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluate.cases import CASES
from evaluate.golden_rag import RAG_GOLDEN
from evaluate.runner import run_batch
from evaluate.judge import judge_batch
from evaluate.metrics import compute_summary, save_results, load_baseline, save_baseline, diff_baseline
from agent.react_agent import ReactAgent
from rag.rag_service import RagSummarizeService


def print_header(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def eval_agent(set_baseline: bool = False):
    """Agent 全链路评测"""
    print_header("Agent 全链路评测")

    agent = ReactAgent()

    # 批量执行
    print(f"\n执行 {len(CASES)} 条测试用例...")
    results = run_batch(agent, CASES, progress_callback=lambda i, t: print(f"  [{i}/{t}]", end="\r"))
    print(f"\n执行完成，耗时 {sum(r.elapsed_seconds for r in results):.1f}s\n")

    # LLM 打分
    print("LLM-as-judge 评分中...")
    judges = judge_batch(CASES, results)

    # 汇总
    summary = compute_summary(CASES, results, judges)
    csv_path = save_results(CASES, results, judges, summary)

    # 输出报告
    print(f"\n通过率: {summary.passed}/{summary.total} = {summary.passed/summary.total*100:.1f}%")
    print(f"Judge 均分: {summary.avg_score}/5")
    print(f"平均工具调用: {summary.avg_tool_calls} 次")
    print(f"平均耗时: {summary.avg_elapsed}s\n")

    print("按场景分类:")
    for cat, stats in sorted(summary.by_category.items()):
        rate = stats["passed"] / stats["total"] * 100 if stats["total"] else 0
        bar = "█" * int(rate / 10) + "░" * (10 - int(rate / 10))
        print(f"  {cat:8s}: {bar} {rate:.0f}% ({stats['passed']}/{stats['total']})  均分 {stats['avg_score']}")

    if summary.failures:
        print(f"\n失败用例 ({len(summary.failures)} 条):")
        for f in summary.failures:
            print(f"  [{f['id']}] {f['category']} | {f['failure']:20s} | score={f['score']} | tools={f['called_tools']}")

    if summary.failure_distribution:
        print(f"\n失败原因分布:")
        for reason, count in sorted(summary.failure_distribution.items(), key=lambda x: -x[1]):
            pct = count / len(summary.failures) * 100
            print(f"  {reason:25s}: {count:2d} ({pct:.0f}%)")

    print(f"\n结果已保存至: {csv_path}")

    # 基线对比
    baseline = load_baseline()
    if baseline:
        diff = diff_baseline(summary, baseline)
        print(diff)
        diff_path = os.path.join(os.path.dirname(csv_path), "diff.txt")
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(diff)
        print(f"差异报告已保存至: {diff_path}")
    elif set_baseline:
        save_baseline(summary)
        print("已设为基线。")

    if not baseline and not set_baseline:
        print("\n提示: 首次运行，建议用 --baseline 将本次结果设为基线。")


def eval_rag():
    """RAG 独立检索评测"""
    print_header("RAG 检索质量评测")
    rag = RagSummarizeService()
    retriever = rag.vector_store.get_retriever()

    total = len(RAG_GOLDEN)
    recall_sum = 0.0
    precision_sum = 0.0

    print(f"\n共 {total} 条评测数据\n")

    for i, g in enumerate(RAG_GOLDEN):
        docs = retriever.invoke(g.query)
        retrieved_files = set()
        for doc in docs:
            source = doc.metadata.get("source", "")
            retrieved_files.add(os.path.basename(source))

        # recall: 应命中的文件里，实际命中了多少
        hits = 0
        for prefix in g.relevant_doc_prefixes:
            for rf in retrieved_files:
                if rf.startswith(prefix):
                    hits += 1
                    break
        recall = hits / len(g.relevant_doc_prefixes) if g.relevant_doc_prefixes else 1.0

        # precision: 检索到的文件里，有多少是相关的
        relevant_retrieved = 0
        for rf in retrieved_files:
            for prefix in g.relevant_doc_prefixes:
                if rf.startswith(prefix):
                    relevant_retrieved += 1
                    break
        precision = relevant_retrieved / len(docs) if docs else 0.0

        recall_sum += recall
        precision_sum += precision

        bar = "█" * int(recall * 10) + "░" * (10 - int(recall * 10))
        print(f"  [{i+1:2d}/{total}] {bar} recall={recall:.2f} precision={precision:.2f}  |  {g.query[:40]}")

    avg_recall = recall_sum / total
    avg_precision = precision_sum / total
    print(f"\n平均 Recall@{3}:  {avg_recall:.2%}")
    print(f"平均 Precision@{3}: {avg_precision:.2%}")


def main():
    set_baseline = "--baseline" in sys.argv
    rag_only = "--rag-only" in sys.argv

    if rag_only:
        eval_rag()
    else:
        eval_agent(set_baseline)


if __name__ == "__main__":
    main()
