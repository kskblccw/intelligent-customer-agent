"""
测试用例定义 — 30 个覆盖各业务场景的用例。

企业规范要求：
- 用例覆盖所有工具和业务场景
- 包含正常路径和边界/异常路径
- 每个用例有明确的通过条件（工具序列 / 关键词 / 禁用词）
"""

from dataclasses import dataclass, field


@dataclass
class TestCase:
    id: str
    category: str
    query: str
    description: str = ""
    expected_tools: list[str] | None = None    # 必须调用的工具，None = 不强制
    forbidden_tools: list[str] = field(default_factory=list)  # 禁止调用的工具
    expected_keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    min_tool_calls: int = 0
    max_tool_calls: int = 10


CASES: list[TestCase] = [
    # ========== 天气 + 保养 (7 条) ==========
    TestCase(
        id="TC01", category="天气保养",
        query="请结合我所在城市的天气，告知一下我如何保养机器人",
        description="标准天气保养链路：定位→天气→RAG保养知识",
        expected_tools=["get_user_location", "get_weather", "rag_summarize"],
        forbidden_tools=["fill_context_for_report", "fetch_external_data"],
        expected_keywords=["保养", "天气"],
        forbidden_keywords=["无参考资料", "无法生成", "未知城市"],
        min_tool_calls=2, max_tool_calls=6,
    ),
    TestCase(
        id="TC02", category="天气保养",
        query="今天深圳32度、湿度80%，我的扫拖机器人要怎么维护",
        description="用户直接提供了城市名，不应再调 get_user_location",
        expected_tools=["get_weather", "rag_summarize"],
        forbidden_tools=["get_user_location"],
        expected_keywords=["深圳", "湿度", "保养"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=2, max_tool_calls=6,
    ),
    TestCase(
        id="TC03", category="天气保养",
        query="广州回南天来了，扫地机要注意什么",
        description="潮湿天气保养，应查询天气并给针对性建议",
        expected_tools=["get_weather", "rag_summarize"],
        expected_keywords=["广州", "湿度", "保养"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=2, max_tool_calls=6,
    ),
    TestCase(
        id="TC04", category="天气保养",
        query="北方冬天干燥，扫地机器人使用有什么特别要注意的",
        description="用户提到了环境条件，应查保养知识",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["保养", "干燥"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=5,
    ),
    TestCase(
        id="TC05", category="天气保养",
        query="下雨天能不能用扫地机器人",
        description="天气+使用场景咨询",
        expected_tools=["get_user_location", "get_weather", "rag_summarize"],
        expected_keywords=["雨", "保养"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=2, max_tool_calls=6,
    ),
    TestCase(
        id="TC06", category="天气保养",
        query="高温天气对扫地机器人电池有影响吗",
        description="天气对硬件的专项影响",
        expected_tools=["get_user_location", "get_weather", "rag_summarize"],
        expected_keywords=["电池", "温度"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=2, max_tool_calls=6,
    ),
    TestCase(
        id="TC07", category="天气保养",
        query="我在的城市经常下雪，机器人能正常工作吗",
        description="极端天气+使用，应定位后查天气",
        expected_tools=["get_user_location", "get_weather", "rag_summarize"],
        expected_keywords=["雪", "保养"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=2, max_tool_calls=6,
    ),

    # ========== 纯保养咨询 (5 条) ==========
    TestCase(
        id="TC08", category="保养咨询",
        query="扫地机器人的滤网多久换一次",
        description="纯 RAG 检索，不涉及天气定位",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "get_weather", "fill_context_for_report", "fetch_external_data"],
        expected_keywords=["滤网", "更换"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC09", category="保养咨询",
        query="边刷缠绕头发了该怎么清理",
        description="故障保养，纯 RAG",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "get_weather", "fill_context_for_report"],
        expected_keywords=["清理", "边刷", "头发"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC10", category="保养咨询",
        query="扫地机器人日常怎么保养，简单说下",
        description="通用保养查询",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "get_weather", "fill_context_for_report"],
        expected_keywords=["保养"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC11", category="保养咨询",
        query="拖布发臭是什么原因，怎么处理",
        description="特定故障 + 保养方案",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["拖布", "发臭", "清理"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC12", category="保养咨询",
        query="集尘袋满了会提示吗，多久清理一次尘盒",
        description="具体耗材维护问题",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["尘盒", "集尘"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),

    # ========== 报告生成 (6 条) ==========
    TestCase(
        id="TC13", category="报告生成",
        query="帮我生成一下我的专属使用报告",
        description="标准报告链路：ID→月份→fill_context→fetch→RAG",
        expected_tools=["get_user_id", "get_current_month", "fill_context_for_report", "fetch_external_data"],
        expected_keywords=["报告", "使用"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=4, max_tool_calls=8,
    ),
    TestCase(
        id="TC14", category="报告生成",
        query="查一下我的机器人6月份的使用记录",
        description="用户指定了月份，不应调 get_current_month",
        expected_tools=["get_user_id", "fill_context_for_report", "fetch_external_data"],
        forbidden_tools=["get_current_month"],
        expected_keywords=["6月", "使用"],
        min_tool_calls=3, max_tool_calls=8,
    ),
    TestCase(
        id="TC15", category="报告生成",
        query="给我做一个扫地机器人的使用总结",
        description="变体措辞的报告生成",
        expected_tools=["get_user_id", "get_current_month", "fill_context_for_report", "fetch_external_data"],
        expected_keywords=["报告", "使用"],
        min_tool_calls=4, max_tool_calls=8,
    ),
    TestCase(
        id="TC16", category="报告生成",
        query="看看我的机器人最近用得怎么样，帮我分析一下",
        description="非正式语气的报告请求",
        expected_tools=["get_user_id", "get_current_month", "fill_context_for_report", "fetch_external_data"],
        expected_keywords=["报告"],
        min_tool_calls=4, max_tool_calls=8,
    ),
    TestCase(
        id="TC17", category="报告生成",
        query="生成一份2025年3月的使用报告",
        description="指定月份的报告",
        expected_tools=["get_user_id", "fill_context_for_report", "fetch_external_data"],
        forbidden_tools=["get_current_month"],
        expected_keywords=["3月", "报告"],
        min_tool_calls=3, max_tool_calls=8,
    ),
    TestCase(
        id="TC18", category="报告生成",
        query="12月份我的扫地机用得频繁吗，帮我出个报告",
        description="指定月份+追问式报告",
        expected_tools=["get_user_id", "fill_context_for_report", "fetch_external_data"],
        forbidden_tools=["get_current_month"],
        expected_keywords=["12月", "报告"],
        min_tool_calls=3, max_tool_calls=8,
    ),

    # ========== 故障排查 (4 条) ==========
    TestCase(
        id="TC19", category="故障排查",
        query="扫地机器人不充电了怎么办",
        description="硬件故障排查，纯 RAG",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report", "fetch_external_data"],
        expected_keywords=["充电", "排查"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC20", category="故障排查",
        query="机器人一直在一个地方转圈，好像迷路了",
        description="行为异常故障",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["迷路", "转圈"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC21", category="故障排查",
        query="扫地机吸力越来越小了，感觉吸不干净",
        description="性能下降问题",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["吸力", "清理"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC22", category="故障排查",
        query="运行时噪音特别大，是不是哪里坏了",
        description="硬件异常噪音",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["噪音", "排查"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),

    # ========== 选购建议 (3 条) ==========
    TestCase(
        id="TC23", category="选购建议",
        query="84平的房子，养了一只猫，适合哪种扫地机器人",
        description="规格化选购建议（RAG 知识库有相关内容）",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report", "fetch_external_data"],
        expected_keywords=["84", "机器人"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC24", category="选购建议",
        query="家里有长毛地毯，推荐一款不会卡住的机器人",
        description="特定场景选购",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["地毯"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),
    TestCase(
        id="TC25", category="选购建议",
        query="预算三千以内，扫拖一体机有什么推荐",
        description="预算敏感型选购",
        expected_tools=["rag_summarize"],
        forbidden_tools=["get_user_location", "fill_context_for_report"],
        expected_keywords=["推荐", "扫拖"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=1, max_tool_calls=3,
    ),

    # ========== 复杂多工具协作 (2 条) ==========
    TestCase(
        id="TC26", category="多工具协作",
        query="结合我的城市天气和使用习惯，帮我全面评估一下扫地机器人的耗材更换周期",
        description="需要定位+天气+使用报告+RAG保养知识的多源融合",
        expected_tools=["get_user_location", "get_weather", "get_user_id",
                        "get_current_month", "fill_context_for_report",
                        "fetch_external_data", "rag_summarize"],
        expected_keywords=["耗材", "更换"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=3, max_tool_calls=10,
    ),
    TestCase(
        id="TC27", category="多工具协作",
        query="广州夏天湿度大，我的机器人在这种环境下怎么调参数能让它更好用",
        description="天气+保养+使用优化",
        expected_tools=["get_weather", "rag_summarize"],
        expected_keywords=["广州", "湿度", "保养"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=2, max_tool_calls=7,
    ),

    # ========== 边界/异常用例 (3 条) ==========
    TestCase(
        id="TC28", category="边界情况",
        query="你好",
        description="纯闲聊不应调用任何工具",
        expected_tools=[],
        forbidden_tools=["rag_summarize", "get_weather", "get_user_location",
                        "get_user_id", "fill_context_for_report", "fetch_external_data"],
        expected_keywords=["扫地", "机器人"],
        max_tool_calls=0,
    ),
    TestCase(
        id="TC29", category="边界情况",
        query="帮我查一下火星的天气，看看我的机器人在火星上怎么用",
        description="不合法的城市名，应优雅处理",
        forbidden_tools=["fill_context_for_report", "fetch_external_data"],
        forbidden_keywords=["无参考资料"],
        min_tool_calls=0, max_tool_calls=5,
    ),
    TestCase(
        id="TC30", category="边界情况",
        query="",
        description="空输入应直接提示，不调任何工具",
        forbidden_tools=["rag_summarize", "get_weather", "get_user_location",
                        "get_user_id", "fill_context_for_report", "fetch_external_data"],
        max_tool_calls=0,
    ),
]


CATEGORIES = sorted(set(c.category for c in CASES))
