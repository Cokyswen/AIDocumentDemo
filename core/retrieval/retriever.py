"""
检索器 - 高层检索接口，支持多种检索方式
"""

import logging
from typing import List, Optional, Dict, Any

from .vector_store import VectorStore, RetrievalResult
from .hybrid_search import HybridSearch
from .bm25_retriever import BM25Retriever
from .reranker import Reranker, rerank_results


class Retriever:
    """统一检索器，支持向量搜索、混合搜索和重排序"""

    def __init__(
        self,
        vector_store: VectorStore,
        top_k: int = 5,
        use_hybrid: bool = False,
        use_rerank: bool = False,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        fusion_method: str = "rrf",
        rerank_method: str = "score",
    ):
        """
        初始化检索器

        Args:
            vector_store: 向量存储实例
            top_k: 默认返回数量
            use_hybrid: 是否使用混合搜索
            use_rerank: 是否使用重排序
            vector_weight: 向量搜索权重
            keyword_weight: 关键词搜索权重
            fusion_method: 融合方法 ("rrf" 或 "weighted_sum")
            rerank_method: 重排序方法 ("score" 或 "diversity")
        """
        self.logger = logging.getLogger(__name__)
        self.vector_store = vector_store
        self.top_k = top_k
        self.use_hybrid = use_hybrid
        self.use_rerank = use_rerank
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.fusion_method = fusion_method
        self.rerank_method = rerank_method

        self._hybrid_search: Optional[HybridSearch] = None
        self._bm25_retriever: Optional[BM25Retriever] = None
        self._last_results: List[RetrievalResult] = []

    def _get_hybrid_search(self) -> HybridSearch:
        """获取或创建混合搜索实例"""
        if self._hybrid_search is None:
            self._hybrid_search = HybridSearch(
                vector_store=self.vector_store,
                bm25_retriever=self._bm25_retriever,
                vector_weight=self.vector_weight,
                keyword_weight=self.keyword_weight,
                fusion_method=self.fusion_method,
            )
        return self._hybrid_search

    def _get_bm25_retriever(self) -> Optional[BM25Retriever]:
        """获取 BM25 检索器"""
        if self._bm25_retriever is None:
            try:
                all_docs = self.vector_store.collection.get(
                    include=["documents", "metadatas"]
                )
                if all_docs.get("documents"):
                    self._bm25_retriever = BM25Retriever(
                        documents=all_docs["documents"],
                        metadatas=all_docs.get("metadatas", []),
                    )
                    self.logger.info(
                        f"BM25 检索器初始化完成，{len(all_docs['documents'])} 个文档"
                    )
            except Exception as e:
                self.logger.warning(f"BM25 检索器初始化失败: {e}")
        return self._bm25_retriever

    def set_hybrid_mode(self, use_hybrid: bool):
        """设置是否使用混合搜索"""
        self.use_hybrid = use_hybrid
        if use_hybrid and self._hybrid_search:
            self._hybrid_search = None

    def set_rerank_mode(self, use_rerank: bool, method: str = "score"):
        """设置是否使用重排序"""
        self.use_rerank = use_rerank
        self.rerank_method = method

    def set_weights(self, vector_weight: float, keyword_weight: float):
        """设置混合搜索权重"""
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        if self._hybrid_search:
            self._hybrid_search.set_weights(vector_weight, keyword_weight)

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 返回数量
            filters: 元数据过滤条件

        Returns:
            检索结果列表
        """
        k = top_k or self.top_k

        try:
            if self.use_hybrid:
                bm25 = self._get_bm25_retriever()
                if bm25:
                    self._hybrid_search = HybridSearch(
                        vector_store=self.vector_store,
                        bm25_retriever=bm25,
                        vector_weight=self.vector_weight,
                        keyword_weight=self.keyword_weight,
                        fusion_method=self.fusion_method,
                    )
                results = self._get_hybrid_search().search(query, top_k=k)
            else:
                results = self.vector_store.search(query, n_results=k, where=filters)

            if self.use_rerank and results:
                results = rerank_results(query, results, k, self.rerank_method)

            self._last_results = results
            self.logger.info(f"检索到 {len(results)} 条结果")
            return results

        except Exception as e:
            self.logger.error(f"检索失败: {e}")
            return []

    def vector_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalResult]:
        """纯向量搜索"""
        k = top_k or self.top_k
        try:
            results = self.vector_store.search(query, n_results=k, where=filters)
            self._last_results = results
            return results
        except Exception as e:
            self.logger.error(f"向量搜索失败: {e}")
            return []

    def keyword_search(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """纯关键词搜索（BM25）"""
        k = top_k or self.top_k
        bm25 = self._get_bm25_retriever()
        if not bm25:
            self.logger.warning("BM25 检索器未初始化")
            return []

        try:
            results = bm25.search(query, top_k=k)
            return [
                RetrievalResult(
                    content=r.content, score=r.score, metadata=r.metadata, rank=r.rank
                )
                for r in results
            ]
        except Exception as e:
            self.logger.error(f"关键词搜索失败: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        top_k: Optional[int] = None,
        vector_weight: Optional[float] = None,
        keyword_weight: Optional[float] = None,
        fusion_method: str = "rrf",
    ) -> List[RetrievalResult]:
        """混合搜索（向量 + 关键词）"""
        k = top_k or self.top_k
        vw = vector_weight or self.vector_weight
        kw = keyword_weight or self.keyword_weight

        bm25 = self._get_bm25_retriever()
        hybrid = HybridSearch(
            vector_store=self.vector_store,
            bm25_retriever=bm25,
            vector_weight=vw,
            keyword_weight=kw,
            fusion_method=fusion_method,
        )
        results = hybrid.search(query, top_k=k)
        self._last_results = results
        return results

    def get_texts(self) -> List[str]:
        """获取检索到的文档内容"""
        return [r.content for r in self._last_results]

    def get_results(self) -> List[RetrievalResult]:
        """获取检索结果"""
        return self._last_results

    def filter_by_source(self, source: str) -> List[RetrievalResult]:
        """按来源过滤"""
        return [r for r in self._last_results if r.metadata.get("source") == source]

    def refresh_bm25_index(self):
        """刷新 BM25 索引"""
        self._bm25_retriever = None
        self._get_bm25_retriever()
