from abc import ABC, abstractmethod
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from typing import  Optional
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
        return ChatOpenAI(model=rag_config["chat_model_name"],base_url=rag_config["base_url"])


class EmbeddingsModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return HuggingFaceEmbeddings(model=rag_config["embedding_model_name"])



chat_model = ChatModelFactory().generator()
embedding_model = EmbeddingsModelFactory().generator()