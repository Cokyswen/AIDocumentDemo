"""
重排序器 - 对检索结果进行重新排序
"""

import logging
import re
from typing import List

from .vector_store import RetrievalResult

logger = logging.getLogger(__name__)


class Reranker:
    """重排序器"""

    def __init__(self, method: str = "score"):
        """
        初始化重排序器

        Args:
            method: 重排序方法
                - "score": 基于分数重排序
                - "diversity": 基于多样性重排序
        """
        self.method = method

    def rerank(
        self, query: str, results: List[RetrievalResult], top_k: int = 5
    ) -> List[RetrievalResult]:
        """对检索结果重排序"""
        if not results:
            return []

        if self.method == "score":
            return self._rerank_by_score(results, top_k)
        elif self.method == "diversity":
            return self._rerank_by_diversity(query, results, top_k)
        else:
            logger.warning(f"未知的重排序方法: {self.method}，使用分数重排序")
            return self._rerank_by_score(results, top_k)

    def _rerank_by_score(
        self, results: List[RetrievalResult], top_k: int
    ) -> List[RetrievalResult]:
        """基于相关性分数重排序"""
        sorted_results = sorted(results, key=lambda x: x.score, reverse=True)

        reranked = []
        for i, result in enumerate(sorted_results[:top_k]):
            reranked.append(
                RetrievalResult(
                    content=result.content,
                    score=result.score,
                    metadata=result.metadata,
                    rank=i + 1,
                )
            )

        return reranked

    def _rerank_by_diversity(
        self, query: str, results: List[RetrievalResult], top_k: int
    ) -> List[RetrievalResult]:
        """基于多样性重排序"""
        if len(results) <= top_k:
            return self._rerank_by_score(results, top_k)

        reranked = [results[0]]
        remaining = results[1:]

        while len(reranked) < top_k and remaining:
            best_score = float("-inf")
            best_idx = 0

            for i, candidate in enumerate(remaining):
                diversity_score = self._calculate_diversity(candidate, reranked)
                combined_score = 0.5 * candidate.score + 0.5 * diversity_score

                if combined_score > best_score:
                    best_score = combined_score
                    best_idx = i

            reranked.append(remaining[best_idx])
            remaining.pop(best_idx)

        for i, result in enumerate(reranked):
            result.rank = i + 1

        return reranked

    def _calculate_diversity(
        self, candidate: RetrievalResult, selected: List[RetrievalResult]
    ) -> float:
        """计算候选结果与已选结果的多样性（使用 Jaccard 距离）"""
        candidate_terms = set(self._extract_terms(candidate.content))
        min_similarity = float("inf")

        for sel in selected:
            selected_terms = set(self._extract_terms(sel.content))
            intersection = len(candidate_terms & selected_terms)
            union = len(candidate_terms | selected_terms)

            if union > 0:
                similarity = intersection / union
                min_similarity = min(min_similarity, 1 - similarity)

        return min_similarity if min_similarity != float("inf") else 1.0

    def _extract_terms(self, text: str) -> List[str]:
        """提取文本中的关键词"""
        chinese = re.findall(r"[\u4e00-\u9fff]+", text)
        english = re.findall(r"[a-zA-Z0-9_]+", text)
        return english + [c for chars in chinese for c in chars]


def rerank_results(
    query: str, results: List[RetrievalResult], top_k: int = 5, method: str = "score"
) -> List[RetrievalResult]:
    """
    便捷函数：对检索结果重排序

    Args:
        query: 查询文本
        results: 检索结果列表
        top_k: 返回结果数量
        method: 重排序方法

    Returns:
        重排序后的结果列表
    """
    reranker = Reranker(method=method)
    return reranker.rerank(query, results, top_k)
