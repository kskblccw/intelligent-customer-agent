# Intelligent Customer Agent

An intelligent customer agent system developed based on the LangChain framework, employing a ReAct (Reasoning + Acting) architecture, supporting multiple tool invocations, RAG knowledge retrieval, and dynamic prompt switching.

## Project Overview

This project is an intelligent customer agent system integrating the following core features:

- **ReAct Intelligent Agent**: A reasoning and action framework based on the ReAct paradigm
- **Tool Invocation**: Supports tools such as weather queries, geolocation retrieval, and user information management
- **RAG Knowledge Retrieval**: Retrieval-augmented generation based on the Chroma vector database
- **Middleware Support**: Tool execution monitoring, logging, and dynamic prompt switching
- **Flexible Configuration**: Customizable models and prompts via YAML configuration files

## Project Structure

```
├── agent/                      # Agent core module
│   ├── react_agent.py          # ReAct agent implementation
│   └── tools/                  # Tools module
│       ├── agent_tools.py      # Various business tools
│       └── middleware.py       # Middleware (monitoring, logging, dynamic prompts)
├── rag/                        # RAG module
│   ├── rag_service.py          # RAG summarization service
│   └── vector_store.py         # Vector storage service
├── model/                      # Model factory
│   └── factory.py              # Chat and embedding model factory
├── config/                     # Configuration files
│   ├── agent.yml               # Agent configuration
│   ├── chroma.yml              # Chroma configuration
│   ├── prompts.yml             # Prompt configuration
│   └── rag.yml                 # RAG configuration
├── prompts/                    # Prompt templates
│   ├── main_prompt.txt         # Main prompt
│   ├── rag_summarize.txt       # RAG summarization prompt
│   └── report_prompt.txt       # Report prompt
├── utils/                      # Utility modules
│   ├── config_handler.py       # Configuration loader
│   ├── file_handler.py         # File handling
│   ├── logger_handler.py       # Logging handler
│   ├── prompt_loader.py        # Prompt loader
│   └── pyth_tool.py            # Python tool
├── data/                       # Data directory
│   └── external/               # External data
│       └── records.csv         # User record data
└── chroma_db/                  # Chroma vector database
```

## Core Features

### 1. ReAct Agent (ReactAgent)

The `ReactAgent` class in `agent/react_agent.py` implements the ReAct reasoning framework, supporting:
- Execution of user queries
- Dynamic invocation of various tools
- Reasoning and action loops

### 2. Tool Set (Agent Tools)

`agent/tools/agent_tools.py` provides the following tools:

| Tool Name | Function Description |
|----------|----------------------|
| `get_weather` | Retrieves weather for a specified city |
| `get_user_location` | Retrieves the user's current city |
| `rag_summarize` | Retrieves reference materials from the vector store |
| `get_user_id` | Retrieves the user ID |
| `get_current_month` | Retrieves the current month |
| `fetch_external_data` | Fetches user usage records from external systems |
| `fill_context_for_report` | Triggers dynamic context injection |

### 3. Middleware

`agent/tools/middleware.py` provides middleware functionality:

- **Tool Monitoring** (`monitor_tool`): Monitors tool execution processes
- **Logging** (`log_before_model`): Logs before model execution
- **Dynamic Prompts** (`report_prompt_switch`): Dynamically switches prompts based on requests

### 4. RAG Service

- **RAG Summarization Service** (`rag/rag_service.py`): Document retrieval and summary generation
- **Vector Storage Service** (`rag/vector_store.py`): Vector storage and retrieval based on Chroma

### 5. Model Factory

`model/factory.py` provides model factory classes:
- `ChatModelFactory`: Chat model factory
- `EmbeddingsModelFactory`: Embedding model factory

## Installation & Configuration

### System Requirements

- Python 3.8+
- LangChain
- Chroma
- Other dependencies listed in the code

### Configuration Instructions

Configure parameters in the `config/` directory:

- **agent.yml**: Agent model configuration
- **chroma.yml**: Vector database configuration
- **prompts.yml**: Prompt configuration
- **rag.yml**: RAG-related configuration

## Usage Example

```python
from agent.react_agent import ReactAgent

# Create agent instance
agent = ReactAgent()

# Execute query
query = "Please check the weather in Beijing"
result = agent.execute(query)
print(result)
```

## Dependencies

Primary dependencies include:
- langchain
- chromadb
- requests
- pyyaml

## Logging

Log files are stored in the `logs/` directory for debugging and monitoring agent execution.

## License

This project is for learning and research purposes only.