"""
RAG 检索独立评测数据集。

企业规范：RAG 检索质量应与 Agent 推理能力解耦评估。
这里的每条数据标注了 query → 应命中的知识文件名前缀，
用于计算 recall@k / precision@k，不依赖 Agent 执行。
"""

from dataclasses import dataclass, field


@dataclass
class RAGGoldenCase:
    query: str
    description: str
    relevant_doc_prefixes: list[str]  # 应命中文件名的前缀（如 "维护保养" 匹配 "维护保养.txt"）


RAG_GOLDEN: list[RAGGoldenCase] = [
    # --- 保养维护 ---
    RAGGoldenCase(
        query="扫地机器人日常怎么保养",
        description="通用保养方法",
        relevant_doc_prefixes=["维护保养"],
    ),
    RAGGoldenCase(
        query="滤网多久换一次",
        description="耗材更换周期",
        relevant_doc_prefixes=["维护保养"],
    ),
    RAGGoldenCase(
        query="边刷缠了头发怎么清理",
        description="滚刷清理方法",
        relevant_doc_prefixes=["维护保养", "故障排除"],
    ),
    RAGGoldenCase(
        query="拖布发臭是什么原因",
        description="拖布异味处理",
        relevant_doc_prefixes=["维护保养", "故障排除"],
    ),
    RAGGoldenCase(
        query="尘盒怎么清理",
        description="尘盒维护",
        relevant_doc_prefixes=["维护保养"],
    ),
    RAGGoldenCase(
        query="扫地机器人多久做一次全面清洁",
        description="定期清洁周期",
        relevant_doc_prefixes=["维护保养"],
    ),

    # --- 故障排查 ---
    RAGGoldenCase(
        query="机器人不充电了",
        description="充电故障",
        relevant_doc_prefixes=["故障排除"],
    ),
    RAGGoldenCase(
        query="扫地机一直在转圈好像迷路了",
        description="导航故障",
        relevant_doc_prefixes=["故障排除"],
    ),
    RAGGoldenCase(
        query="吸力变小吸不干净怎么办",
        description="吸力下降",
        relevant_doc_prefixes=["故障排除", "维护保养"],
    ),
    RAGGoldenCase(
        query="运行噪音特别大",
        description="异常噪音",
        relevant_doc_prefixes=["故障排除"],
    ),
    RAGGoldenCase(
        query="扫地机器人连不上WiFi了",
        description="连接故障",
        relevant_doc_prefixes=["故障排除", "扫地机器人100问"],
    ),

    # --- 选购建议 ---
    RAGGoldenCase(
        query="84平房子养猫适合什么扫地机器人",
        description="户型+宠物选购",
        relevant_doc_prefixes=["选购指南", "扫地机器人100问"],
    ),
    RAGGoldenCase(
        query="长毛地毯推荐不卡住的机器人",
        description="地毯场景选购",
        relevant_doc_prefixes=["选购指南"],
    ),
    RAGGoldenCase(
        query="预算三千扫拖一体机推荐",
        description="预算选购",
        relevant_doc_prefixes=["选购指南", "扫拖一体机器人100问"],
    ),
    RAGGoldenCase(
        query="扫拖一体和单扫地有什么区别",
        description="品类对比",
        relevant_doc_prefixes=["扫拖一体机器人100问", "选购指南"],
    ),

    # --- 天气/环境相关 ---
    RAGGoldenCase(
        query="潮湿天气扫地机器人怎么保养",
        description="潮湿环境保养",
        relevant_doc_prefixes=["维护保养"],
    ),
    RAGGoldenCase(
        query="高温对电池有影响吗",
        description="温度影响",
        relevant_doc_prefixes=["维护保养", "故障排除"],
    ),
    RAGGoldenCase(
        query="下雪天扫地机器人能用吗",
        description="极端天气使用",
        relevant_doc_prefixes=["维护保养"],
    ),

    # --- 通用问答 ---
    RAGGoldenCase(
        query="扫地机器人水箱怎么加水和清洁",
        description="水箱维护",
        relevant_doc_prefixes=["维护保养"],
    ),
    RAGGoldenCase(
        query="扫地机器人传感器脏了怎么处理",
        description="传感器维护",
        relevant_doc_prefixes=["维护保养", "故障排除"],
    ),
]


# 所有可检索的知识文件名（用于计算 recall 的分母）
EXPECTED_DOC_FILES = [
    "维护保养.txt",
    "故障排除.txt",
    "选购指南.txt",
    "扫地机器人100问.pdf",
    "扫地机器人100问2.txt",
    "扫拖一体机器人100问.txt",
]
