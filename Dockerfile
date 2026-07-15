FROM python:3.12-slim

WORKDIR /app

# 使用 HuggingFace 镜像（国内加速）
ENV HF_ENDPOINT=https://hf-mirror.com \
    HF_HUB_OFFLINE=0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn

# 预下载 HuggingFace 模型
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('BAAI/bge-small-zh-v1.5'); \
SentenceTransformer('BAAI/bge-reranker-v2-m3') \
"

# 复制应用代码
COPY . .

# 恢复离线模式
ENV HF_HUB_OFFLINE=1

# 声明卷
VOLUME ["/app/chroma_db", "/app/logs", "/app/storage", "/app/data"]

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
