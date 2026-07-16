"""
检索服务类 — 混合检索（BM25 + 向量 → RRF 融合 → Cross-encoder 重排），
直接返回检索到的参考资料原文，由 Agent 自行综合生成回答。

企业规范：
- 检索与生成解耦，不在检索工具内部调 LLM
- BM25 保证关键词/型号/术语精确命中
- 向量检索保证语义泛化
- RRF 融合避免分数尺度不一致
- 重排序做精细相关性判断
"""

import os
import pickle

from rag.vector_store import VectorStoreService
from rag.hybrid_retriever import HybridRetriever, Reranker
from utils.logger_handler import logger
from utils.pyth_tool import get_abs_path
from langchain_core.documents import Document

def _is_model_cached(model_name: str) -> bool:
    """检查 HuggingFace 模型是否已在本地缓存，避免启动时触发下载"""
    import os as _os
    hub_cache = _os.path.join(_os.path.expanduser("~"), ".cache", "huggingface", "hub")
    model_dir = "models--" + model_name.replace("/", "--")
    full_path = _os.path.join(hub_cache, model_dir)
    return _os.path.isdir(full_path) and any(
        f.endswith((".safetensors", ".bin"))
        for _root, _dirs, files in _os.walk(full_path)
        for f in files
    )


# 配置项
USE_RERANKER = True          # 是否启用 Cross-encoder 重排序
VECTOR_K = 10                # 向量检索召回数
BM25_K = 10                  # BM25 召回数
FINAL_K = 5                  # RRF 融合后取 top N
RERANKER_TOP_N = 5           # 重排序后取 top N
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"


class RagSummarizeService(object):
    _CORPUS_CACHE = get_abs_path("storage/bm25_corpus.pkl")

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.chain = None  # 保留属性避免旧引用报错，不再使用

        # 尝试从缓存加载 BM25 语料库，避免每次启动都重建
        corpus = self._load_cached_corpus()
        self.retriever = HybridRetriever(
            vector_retriever=self.vector_store.get_retriever(),
            corpus=corpus,
            vector_k=VECTOR_K,
            bm25_k=BM25_K,
            final_k=FINAL_K,
        )
        logger.info(
            f"[RagSummarizeService]混合检索器就绪 "
            f"vector_k={VECTOR_K} bm25_k={BM25_K} final_k={FINAL_K} "
            f"corpus_size={len(corpus)}"
        )

        # 重排序器（可选，仅在模型已缓存时加载，避免启动时下载卡死）
        self.reranker = None
        if USE_RERANKER and _is_model_cached(RERANKER_MODEL):
            try:
                self.reranker = Reranker(model_name=RERANKER_MODEL, top_n=RERANKER_TOP_N)
                logger.info(f"[RagSummarizeService]重排序器就绪 model={RERANKER_MODEL}")
            except Exception as e:
                logger.warning(f"[RagSummarizeService]重排序器加载失败，降级为纯混合检索: {str(e)}")
        elif USE_RERANKER:
            logger.info(
                f"[RagSummarizeService]重排序器模型未缓存，跳过加载"
                f"（首次使用需联网下载 model={RERANKER_MODEL}）"
            )

    def _load_cached_corpus(self) -> list[Document]:
        """从磁盘缓存加载语料库，若缓存失效则从 ChromaDB 重建并写缓存"""
        current_count = self.vector_store.collection_count()
        if os.path.exists(self._CORPUS_CACHE):
            try:
                with open(self._CORPUS_CACHE, "rb") as f:
                    cache = pickle.load(f)
                if cache.get("count") == current_count:
                    logger.info(f"[RagSummarizeService]从缓存加载 BM25 语料库 corpus_size={current_count}")
                    return cache.get("corpus", [])
            except Exception as e:
                logger.warning(f"[RagSummarizeService]语料库缓存读取失败，将重建: {e}")

        logger.info(f"[RagSummarizeService]重建 BM25 语料库 corpus_size={current_count}")
        corpus = self.vector_store.get_all_documents()
        self._save_cache(corpus, current_count)
        return corpus

    def _save_cache(self, corpus: list[Document], count: int):
        """将语料库持久化到磁盘"""
        try:
            os.makedirs(os.path.dirname(self._CORPUS_CACHE), exist_ok=True)
            with open(self._CORPUS_CACHE, "wb") as f:
                pickle.dump({"count": count, "corpus": corpus}, f)
            logger.info(f"[RagSummarizeService]语料库缓存已写入 corpus_size={count}")
        except Exception as e:
            logger.warning(f"[RagSummarizeService]语料库缓存写入失败: {e}")

    def retriever_docs(self, query: str) -> list[Document]:
        """混合检索 → 重排序，返回文档列表"""
        docs = self.retriever.search(query)
        if self.reranker is not None and docs:
            docs = self.reranker.rerank(query, docs)
        return docs

    def rag_search(self, query: str) -> str:
        """检索知识库，直接返回参考资料原文（不调 LLM 总结）"""
        docs = self.retriever_docs(query)
        if not docs:
            return "未检索到相关参考资料。"

        parts = []
        for i, doc in enumerate(docs):
            source = doc.metadata.get("source", "未知来源")
            parts.append(f"【参考资料{i + 1}】（来源: {source}）\n{doc.page_content}")
        return "\n\n".join(parts)

    def refresh_corpus(self):
        """外部新增/删除文档后调用，重建 BM25 索引并更新磁盘缓存"""
        corpus = self.vector_store.get_all_documents()
        self.retriever.update_corpus(corpus)
        self._save_cache(corpus, len(corpus))
        logger.info(f"[RagSummarizeService]语料库已刷新 corpus_size={len(corpus)}")


if __name__ == "__main__":
    service = RagSummarizeService()
    print(service.rag_search("84平的房子，适合哪些扫地机器人"))

