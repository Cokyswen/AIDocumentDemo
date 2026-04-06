"""
混合搜索 - 结合向量搜索和关键词搜索
"""

import logging
from typing import List, Optional, Tuple
from dataclasses import replace

from .vector_store import VectorStore, RetrievalResult
from .bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


class HybridSearch:
    """混合搜索引擎"""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_retriever: Optional[BM25Retriever] = None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        fusion_method: str = "rrf",
    ):
        """
        初始化混合搜索

        Args:
            vector_store: 向量存储实例
            bm25_retriever: BM25检索器实例
            vector_weight: 向量搜索权重
            keyword_weight: 关键词搜索权重
            fusion_method: 融合方法 ("rrf" 或 "weighted_sum")
        """
        self.vector_store = vector_store
        self.bm25_retriever = bm25_retriever
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.fusion_method = fusion_method

    def search(
        self,
        query: str,
        top_k: int = 5,
        vector_top_k: Optional[int] = None,
        keyword_top_k: Optional[int] = None,
    ) -> List[RetrievalResult]:
        """
        执行混合搜索

        Args:
            query: 查询文本
            top_k: 最终返回结果数量
            vector_top_k: 向量搜索返回数量
            keyword_top_k: 关键词搜索返回数量

        Returns:
            融合后的检索结果
        """
        if vector_top_k is None:
            vector_top_k = top_k * 2
        if keyword_top_k is None:
            keyword_top_k = top_k * 2

        vector_results = []
        keyword_results = []

        vector_results = self.vector_store.search(query, n_results=vector_top_k)

        if self.bm25_retriever:
            bm25_results = self.bm25_retriever.search(query, top_k=keyword_top_k)
            keyword_results = [
                RetrievalResult(
                    content=r.content, score=r.score, metadata=r.metadata, rank=r.rank
                )
                for r in bm25_results
            ]

        fused = self._fuse_results(vector_results, keyword_results, top_k)
        logger.info(
            f"混合搜索完成，向量:{len(vector_results)}, 关键词:{len(keyword_results)}, 融合:{len(fused)}"
        )

        return fused

    def _fuse_results(
        self,
        vector_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult],
        top_k: int,
    ) -> List[RetrievalResult]:
        """融合向量和关键词搜索结果"""
        if self.fusion_method == "rrf":
            return self._reciprocal_rank_fusion(vector_results, keyword_results, top_k)
        elif self.fusion_method == "weighted_sum":
            return self._weighted_sum_fusion(vector_results, keyword_results, top_k)
        else:
            logger.warning(f"未知的融合方法: {self.fusion_method}，使用 RRF")
            return self._reciprocal_rank_fusion(vector_results, keyword_results, top_k)

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult],
        top_k: int,
        k: int = 60,
    ) -> List[RetrievalResult]:
        """
        倒数排名融合 (RRF) 算法

        RRF score = sum(weight / (k + rank))
        """
        rrf_scores = {}

        for result in vector_results:
            content = result.content
            if content not in rrf_scores:
                rrf_scores[content] = {"result": result, "score": 0.0}
            rrf_scores[content]["score"] += self.vector_weight * (
                1.0 / (k + result.rank)
            )

        for result in keyword_results:
            content = result.content
            if content not in rrf_scores:
                rrf_scores[content] = {"result": result, "score": 0.0}
            rrf_scores[content]["score"] += self.keyword_weight * (
                1.0 / (k + result.rank)
            )

        sorted_results = sorted(
            rrf_scores.items(), key=lambda x: x[1]["score"], reverse=True
        )

        fused = []
        for i, (content, data) in enumerate(sorted_results[:top_k]):
            result = data["result"]
            fused.append(
                RetrievalResult(
                    content=result.content,
                    score=data["score"],
                    metadata=result.metadata,
                    rank=i + 1,
                )
            )

        return fused

    def _weighted_sum_fusion(
        self,
        vector_results: List[RetrievalResult],
        keyword_results: List[RetrievalResult],
        top_k: int,
    ) -> List[RetrievalResult]:
        """加权求和融合"""
        results_map = {}

        max_vector = max([r.score for r in vector_results]) if vector_results else 1.0
        for result in vector_results:
            content = result.content
            norm_score = result.score / max_vector if max_vector > 0 else 0.0
            if content not in results_map:
                results_map[content] = {"result": result, "score": 0.0}
            results_map[content]["score"] += self.vector_weight * norm_score

        max_keyword = (
            max([r.score for r in keyword_results]) if keyword_results else 1.0
        )
        for result in keyword_results:
            content = result.content
            norm_score = result.score / max_keyword if max_keyword > 0 else 0.0
            if content not in results_map:
                results_map[content] = {"result": result, "score": 0.0}
            results_map[content]["score"] += self.keyword_weight * norm_score

        sorted_results = sorted(
            results_map.items(), key=lambda x: x[1]["score"], reverse=True
        )

        fused = []
        for i, (content, data) in enumerate(sorted_results[:top_k]):
            result = data["result"]
            fused.append(
                RetrievalResult(
                    content=result.content,
                    score=data["score"],
                    metadata=result.metadata,
                    rank=i + 1,
                )
            )

        return fused

    def set_weights(self, vector_weight: float, keyword_weight: float):
        """设置搜索权重"""
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    def set_bm25_retriever(self, retriever: BM25Retriever):
        """设置 BM25 检索器"""
        self.bm25_retriever = retriever
