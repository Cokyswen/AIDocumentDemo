"""
检索配置模型
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RetrievalResult:
    """检索结果"""

    content: str
    score: float
    metadata: dict = field(default_factory=dict)
    rank: int = 0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
            "rank": self.rank,
        }


@dataclass
class RetrievalConfig:
    """检索配置"""

    top_k: int = 5
    collection_name: str = "document_collection"
    use_hybrid: bool = False
    use_rerank: bool = False
    vector_weight: float = 0.7
    keyword_weight: float = 0.3
    fusion_method: str = "rrf"
    rerank_top_k: int = 5


@dataclass
class HybridSearchResult:
    """混合搜索结果"""

    vector_results: List[RetrievalResult] = field(default_factory=list)
    keyword_results: List[RetrievalResult] = field(default_factory=list)
    fused_results: List[RetrievalResult] = field(default_factory=list)
