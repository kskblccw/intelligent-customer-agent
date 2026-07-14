"""
混合检索引擎 — BM25（关键词）+ 向量（语义）→ RRF 融合 → Cross-encoder 重排序。

企业规范：
- 关键词匹配和语义匹配互补，不互相替代
- RRF（Reciprocal Rank Fusion）融合，无需分数归一化
- 重排序作为可选增强，用 Cross-encoder 做精细相关性判断

参考：中期总结中提及的 BM25+向量混合检索 + Re-ranker 重排
"""
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_community.retrievers import BM25Retriever


def _tokenize(text: str) -> list[str]:
    """中文按字符切分，英文/数字保持连续"""
    tokens: list[str] = []
    buf = ""
    for ch in text:
        if ch.isalpha() or ch.isdigit():
            buf += ch
        else:
            if buf:
                tokens.append(buf.lower())
                buf = ""
            if ch.strip():
                tokens.append(ch)
    if buf:
        tokens.append(buf.lower())
    return tokens


class HybridRetriever:
    """BM25 + 向量混合检索器，RRF 融合"""

    def __init__(
        self,
        vector_retriever: BaseRetriever,
        corpus: list[Document],
        vector_k: int = 10,
        bm25_k: int = 10,
        final_k: int = 5,
        rrf_k: int = 60,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
    ):
        self.vector_retriever = vector_retriever
        self.vector_k = vector_k
        self.bm25_k = bm25_k
        self.final_k = final_k
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

        self._bm25: BM25Retriever | None = None
        self._corpus: list[Document] = []
        self._build_bm25(corpus)

    def _build_bm25(self, corpus: list[Document]):
        """（重）构建 BM25 索引"""
        self._corpus = list(corpus)
        if self._corpus:
            self._bm25 = BM25Retriever.from_documents(
                self._corpus,
                preprocess_func=_tokenize,
            )
            self._bm25.k = self.bm25_k
        else:
            self._bm25 = None

    def update_corpus(self, corpus: list[Document]):
        """新增文档后更新语料库并重建 BM25"""
        self._build_bm25(corpus)

    def search(self, query: str) -> list[Document]:
        """混合检索：双向召回 → RRF 融合"""
        # 向量召回
        self.vector_retriever.search_kwargs["k"] = self.vector_k
        vector_docs = self.vector_retriever.invoke(query)

        # BM25 召回
        if self._bm25 is not None:
            self._bm25.k = self.bm25_k
            bm25_docs = self._bm25.invoke(query)
        else:
            bm25_docs = []

        # RRF 融合（用 page_content 去重）
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        for rank, doc in enumerate(vector_docs):
            key = doc.page_content[:120]  # 用内容前缀做去重 key
            rrf_scores[key] = rrf_scores.get(key, 0) + self.vector_weight / (self.rrf_k + rank + 1)
            doc_map[key] = doc

        for rank, doc in enumerate(bm25_docs):
            key = doc.page_content[:120]
            rrf_scores[key] = rrf_scores.get(key, 0) + self.bm25_weight / (self.rrf_k + rank + 1)
            doc_map[key] = doc

        sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        fused = [doc_map[k] for k in sorted_keys[:self.final_k]]

        return fused if fused else vector_docs[:self.final_k]


class Reranker:
    """Cross-encoder 重排序器 — 对候选文档做精细相关性打分"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", top_n: int = 5):
        from sentence_transformers import CrossEncoder  # 延迟导入，避免启动时加载
        self.model = CrossEncoder(model_name)
        self.top_n = top_n

    def rerank(self, query: str, docs: list[Document]) -> list[Document]:
        """对候选文档重排序，返回 top_n 高相关文档"""
        if not docs:
            return []
        # 构造query-doc配对
        pairs = [(query, doc.page_content) for doc in docs]
        scores = self.model.predict(pairs)

        # 安全处理numpy数组，转为一维分数列表
        if hasattr(scores, "flatten"):
            scores = scores.flatten().tolist()
        elif hasattr(scores, "tolist"):
            scores = scores.tolist()

        # 文档与分数配对、降序排序
        ranked_pairs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        # 截取top_n并只返回文档对象
        return [doc for doc, _score in ranked_pairs[:self.top_n]]


def create_hybrid_retriever(
    vector_retriever: BaseRetriever,
    corpus: list[Document],
    use_reranker: bool = False,
    vector_k: int = 10,
    bm25_k: int = 10,
    final_k: int = 5,
    reranker_top_n: int = 5,
) -> HybridRetriever:
    """工厂函数：创建混合检索器，内部自动构建 BM25 索引"""
    return HybridRetriever(
        vector_retriever=vector_retriever,
        corpus=corpus,
        vector_k=vector_k,
        bm25_k=bm25_k,
        final_k=final_k if not use_reranker else reranker_top_n,
    )
