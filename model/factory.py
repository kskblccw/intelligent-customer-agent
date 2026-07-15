"""
模型工厂 — 单例模式，chat_model 和 embedding_model 均模块级懒加载。

为加速启动：
- 设置 HF_HUB_OFFLINE=1 阻止 huggingface_hub 在 import 时做网络验证
- embedding 模型已本地缓存，离线模式秒级加载
"""

from abc import ABC, abstractmethod
import os

# 阻止 HuggingFace Hub 在 import / init 时尝试联网验证模型
# embedding 和 reranker 模型均已在本地缓存或通过 _is_model_cached 检查
if os.environ.get("HF_HUB_OFFLINE") is None:
    os.environ["HF_HUB_OFFLINE"] = "1"

from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from utils.config_handler import rag_config
from langchain_huggingface import HuggingFaceEmbeddings


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        return ChatOpenAI(
            model=rag_config["chat_model_name"],
            base_url=rag_config["base_url"],
            api_key=api_key,
            max_retries=3,
            timeout=60,
        )


class EmbeddingsModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return HuggingFaceEmbeddings(
            model_name=rag_config["embedding_model_name"],
            model_kwargs={"local_files_only": True},
        )


_chat_model: BaseChatModel | None = None
_embedding_model: Embeddings | None = None


def get_chat_model() -> BaseChatModel:
    global _chat_model
    if _chat_model is None:
        _chat_model = ChatModelFactory().generator()
    return _chat_model


def get_embedding_model() -> Embeddings:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingsModelFactory().generator()
    return _embedding_model