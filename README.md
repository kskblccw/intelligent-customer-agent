# 智能扫地机器人维保客服

> 基于 LangGraph ReAct Agent 的企业级智能客服系统。混合检索、工具调用、评测体系、会话持久化。

[English](README.en.md)

---

## 项目架构

```
├── agent/                      # Agent 核心
│   ├── react_agent.py          # ReAct Agent (LangGraph create_agent)
│   └── tools/
│       ├── agent_tools.py      # 7 个工具
│       └── middleware.py        # 中间件：监控/日志/动态提示词切换/重试
├── rag/                        # RAG 检索引擎
│   ├── hybrid_retriever.py     # BM25 + 向量混合检索 + RRF 融合 + Cross-encoder 重排
│   ├── rag_service.py          # 检索服务（检索与 LLM 总结解耦）
│   └── vector_store.py         # ChromaDB 向量存储 + 文档管理
├── model/
│   └── factory.py              # DeepSeek + BGE Embedding
├── storage/
│   └── conversation_store.py   # SQLite 会话持久化
├── evaluate/                   # 评测体系
│   ├── cases.py                # 30 条测试用例（7 类场景）
│   ├── golden_rag.py           # RAG 检索标注数据集（20 条）
│   ├── runner.py               # 批量执行 + trace 收集
│   ├── judge.py                # LLM-as-judge 四维度打分
│   ├── metrics.py              # 汇总统计 + 基线对比
│   └── run.py                  # 一键运行入口
├── utils/                      # 配置、日志、文件、路径、Prompt
├── config/                     # YAML 配置
├── prompts/                    # Prompt 模板
├── data/                       # 知识库文件
└── app.py                      # Streamlit 前端
```

## 核心特性

### RAG 检索链路

| 环节 | 技术 |
|------|------|
| 文档解析 | PyPDFLoader / TextLoader |
| 文本分块 | RecursiveCharacterTextSplitter (200/20) |
| 向量化 | BGE-small-zh-v1.5 |
| 向量存储 | ChromaDB，MD5 去重，启动自动加载 |
| 关键词检索 | BM25 (rank-bm25)，中文按字符切分 |
| 混合融合 | RRF (Reciprocal Rank Fusion)，k=60 |
| 重排序 | BGE-reranker-v2-m3 Cross-encoder（网络不通时自动降级） |
| 结果输出 | 直接返回原始参考资料，由 Agent 自行综合 |

### Agent 引擎

- **ReAct 循环**：LangGraph `create_agent` 驱动思考→行动→观察→再思考
- **7 个工具**：`rag_search` / `get_weather` / `get_user_location` / `get_user_id` / `get_current_month` / `fetch_external_data` / `fill_context_for_report`
- **动态提示词切换**：报告场景自动切换到 `report_prompt.txt`
- **企业级重试**：指数退避 + 随机抖动，`TransientAPIError` 区分瞬时/永久错误
- **上下文压缩**：超出 20 条消息自动 LLM 摘要压缩

### 评测体系

```

场景分布:
  边界情况    
  保养咨询    
  故障排查    
  多工具协作   
  报告生成     
  天气保养     
  选购建议    
```

```bash
python -m evaluate.run              # 全链路评测
python -m evaluate.run --baseline    # 设为基线
python -m evaluate.run --rag-only    # RAG 独立评测
```

### 工程化

- **会话持久化**：SQLite，多会话切换/删除，自动标题
- **知识库管理**：启动自动加载、页面上传入库、MD5 去重
- **日志轮转**：RotatingFileHandler 按 10MB 自动切分
- **懒加载启动**：RAG 服务、Embedding、Reranker 延迟初始化

## 快速开始

### 环境

- Python 3.12+
- Windows / macOS / Linux

### 安装

```bash
git clone <repo-url> && cd intelligent-customer-agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 配置

**`config/rag.yml`**

```yaml
chat_model_name: deepseek-v4-flash
embedding_model_name: BAAI/bge-small-zh-v1.5
base_url: https://api.deepseek.com
```

**`config/agent.yml`**

```yaml
gaodekey: <高德地图 API Key>    # https://lbs.amap.com/
```

**环境变量**

```bash
export DEEPSEEK_API_KEY=<your-key>   # Windows: set DEEPSEEK_API_KEY=xxx
```

### 初始化知识库

首次启动自动加载 `data/` 目录下的文件。也可手动：

```bash
python rag/vector_store.py
```

### 启动

```bash
streamlit run app.py
```

### 运行评测

```bash
python -m evaluate.run              # 全链路 30 条用例
python -m evaluate.run --baseline    # 首次跑完设为基线
python -m evaluate.run --rag-only    # 仅评测 RAG 检索
```

## 技术栈

| 层 | 技术 |
|---|---|
| Agent 框架 | LangGraph (create_agent) |
| LLM | DeepSeek V4 (OpenAI 兼容 API) |
| Embedding | BAAI/bge-small-zh-v1.5 |
| 向量数据库 | ChromaDB |
| 关键词检索 | BM25 (rank-bm25) |
| 重排序 | BAAI/bge-reranker-v2-m3 |
| 前端 | Streamlit |
| 持久化 | SQLite |
| 外部 API | 高德地图（天气 + IP 定位） |
| 日志 | RotatingFileHandler |

## 面试要点

围绕这个项目可以深入聊的话题：

- **为什么用 RRF 而不是分数加权融合？** — BM25 和向量分数的尺度不可比，RRF 只依赖排名，天然解决归一化问题
- **ReAct 是 LLM 自带的还是框架做的？** — LLM function calling × System Prompt × LangGraph StateGraph 执行循环，三层协作
- **检索和生成为什么要解耦？** — 工具内部不应调 LLM 总结，返回原文让 Agent 综合，省 token 且信息不丢失
- **怎么处理工具调用失败？** — `TransientAPIError` 标记可重试错误 → 中间件指数退避 → 永久失败让 Agent ReAct 换思路
- **评测体系怎么设计的？** — 30 条用例 × LLM-as-judge × 失败 8 分类 × 基线对比，不只是看通过率
- **上下文怎么管理？** — LLM 摘要压缩超出的旧消息，保留关键信息（身份、偏好、诉求），丢弃冗余步骤

## 许可

MIT
