# 智能客服代理 (Intelligent Customer Agent)

基于 LangChain 框架开发的智能客服代理系统，采用 ReAct (Reasoning + Acting) 架构，支持多种工具调用、RAG 知识检索和动态提示词切换。

## 项目简介

本项目是一个智能客服代理系统，集成了以下核心功能：

- **ReAct 智能代理**：基于 ReAct 范式的推理与行动框架
- **工具调用**：支持天气查询、地理位置获取、用户信息管理等工具
- **RAG 知识检索**：基于 Chroma 向量数据库的检索增强生成
- **中间件支持**：工具执行监控、日志记录、动态提示词切换
- **灵活配置**：支持 YAML 配置文件自定义模型、提示词等

## 项目结构

```
├── agent/                      # 代理核心模块
│   ├── react_agent.py          # ReAct 代理实现
│   └── tools/                  # 工具模块
│       ├── agent_tools.py      # 各种业务工具
│       └── middleware.py       # 中间件（监控、日志、动态提示词）
├── rag/                        # RAG 模块
│   ├── rag_service.py         # RAG 摘要服务
│   └── vector_store.py         # 向量存储服务
├── model/                      # 模型工厂
│   └── factory.py              # 聊天模型和嵌入模型工厂
├── config/                     # 配置文件
│   ├── agent.yml              # 代理配置
│   ├── chroma.yml             # Chroma 配置
│   ├── prompts.yml            # 提示词配置
│   └── rag.yml                # RAG 配置
├── prompts/                    # 提示词模板
│   ├── main_prompt.txt        # 主提示词
│   ├── rag_summarize.txt      # RAG 摘要提示词
│   └── report_prompt.txt      # 报告提示词
├── utils/                      # 工具模块
│   ├── config_handler.py      # 配置加载
│   ├── file_handler.py        # 文件处理
│   ├── logger_handler.py      # 日志处理
│   ├── prompt_loader.py       # 提示词加载
│   └── pyth_tool.py           # Python 工具
├── data/                       # 数据目录
│   └── external/              # 外部数据
│       └── records.csv        # 用户记录数据
└── chroma_db/                  # Chroma 向量数据库
```

## 核心功能

### 1. ReAct 代理 (ReactAgent)

`agent/react_agent.py` 中的 `ReactAgent` 类实现了 ReAct 推理框架，支持：
- 执行用户查询
- 动态调用各种工具
- 推理与行动循环

### 2. 工具集 (Agent Tools)

`agent/tools/agent_tools.py` 提供以下工具：

| 工具名称 | 功能描述 |
|---------|---------|
| `get_weather` | 获取指定城市天气 |
| `get_user_location` | 获取用户所在城市 |
| `rag_summarize` | 从向量存储检索参考资料 |
| `get_user_id` | 获取用户ID |
| `get_current_month` | 获取当前月份 |
| `fetch_external_data` | 获取外部系统用户使用记录 |
| `fill_context_for_report` | 触发上下文动态注入 |

### 3. 中间件 (Middleware)

`agent/tools/middleware.py` 提供中间件功能：

- **工具监控** (`monitor_tool`)：监控工具执行过程
- **日志记录** (`log_before_model`)：在模型执行前输出日志
- **动态提示词** (`report_prompt_switch`)：根据请求动态切换提示词

### 4. RAG 服务

- **RAG 摘要服务** (`rag/rag_service.py`)：文档检索与摘要生成
- **向量存储服务** (`rag/vector_store.py`)：基于 Chroma 的向量存储与检索

### 5. 模型工厂

`model/factory.py` 提供了模型工厂类：
- `ChatModelFactory`：聊天模型工厂
- `EmbeddingsModelFactory`：嵌入模型工厂

## 安装配置

### 环境要求

- Python 3.8+
- LangChain
- Chroma
- 其他依赖见代码

### 配置说明

在 `config/` 目录下配置各项参数：

- **agent.yml**：代理模型配置
- **chroma.yml**：向量数据库配置
- **prompts.yml**：提示词配置
- **rag.yml**：RAG 相关配置

## 使用示例

```python
from agent.react_agent import ReactAgent

# 创建代理实例
agent = ReactAgent()

# 执行查询
query = "请帮我查询北京的天气"
result = agent.execute(query)
print(result)
```

## 依赖项

主要依赖包括：
- langchain
- chromadb
- requests
- pyyaml

## 日志

日志文件保存在 `logs/` 目录下，可用于调试和监控代理执行过程。

## 许可证

本项目仅供学习和研究使用。