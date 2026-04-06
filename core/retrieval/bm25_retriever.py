"""
BM25 关键词检索器
"""

import logging
import re
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BM25Result:
    """BM25检索结果"""

    content: str
    score: float
    metadata: dict
    rank: int = 0


class BM25Retriever:
    """基于 BM25 算法的关键词检索器"""

    def __init__(self, documents: List[str], metadatas: Optional[List[dict]] = None):
        """
        初始化 BM25 检索器

        Args:
            documents: 文档列表
            metadatas: 文档元数据列表
        """
        self.documents = documents
        self.metadatas = metadatas or [{"index": i} for i in range(len(documents))]
        self.bm25 = None
        self._build_index()

    def _build_index(self):
        """构建 BM25 索引"""
        try:
            from rank_bm25 import BM25Okapi

            if self.documents:
                tokenized_docs = []
                for doc in self.documents:
                    tokens = self._tokenize(doc)
                    tokenized_docs.append(tokens)

                self.bm25 = BM25Okapi(tokenized_docs)
                logger.info(f"BM25 索引构建完成，{len(self.documents)} 个文档")
            else:
                self.bm25 = None

        except ImportError:
            logger.warning("rank-bm25 未安装，使用简单关键词匹配")
            self.bm25 = None

    def _tokenize(self, text: str) -> List[str]:
        """分词 - 支持中英文，使用bigram"""
        english_words = re.findall(r"[a-zA-Z0-9_]+", text.lower())

        chinese_text = re.sub(r"[a-zA-Z0-9_\s]", "", text)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", chinese_text)

        chinese_bigrams = []
        for i in range(len(chinese_chars) - 1):
            bigram = chinese_chars[i] + chinese_chars[i + 1]
            chinese_bigrams.append(bigram)

        chinese_phrases = re.findall(r"[\u4e00-\u9fff]{2,}", chinese_text)

        return english_words + chinese_bigrams + [c for c in chinese_chars]

    def search(self, query: str, top_k: int = 5) -> List[BM25Result]:
        """
        搜索相关文档

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        if not self.documents:
            return []

        if self.bm25 is not None:
            return self._bm25_search(query, top_k)
        else:
            return self._simple_search(query, top_k)

    def _bm25_search(self, query: str, top_k: int) -> List[BM25Result]:
        """使用 BM25 搜索"""
        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
            :top_k
        ]

        results = []
        for rank, idx in enumerate(top_indices):
            if scores[idx] > 0:
                results.append(
                    BM25Result(
                        content=self.documents[idx],
                        score=float(scores[idx]),
                        metadata=self.metadatas[idx]
                        if idx < len(self.metadatas)
                        else {},
                        rank=rank + 1,
                    )
                )

        return results

    def _simple_search(self, query: str, top_k: int) -> List[BM25Result]:
        """简单关键词搜索（降级方案）"""
        keywords = self._tokenize(query)
        results = []

        for i, doc in enumerate(self.documents):
            doc_lower = doc.lower()
            matches = sum(1 for kw in keywords if kw.lower() in doc_lower)
            if matches > 0:
                score = matches / len(keywords)
                results.append(
                    BM25Result(
                        content=doc,
                        score=score,
                        metadata=self.metadatas[i] if i < len(self.metadatas) else {},
                        rank=0,
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:top_k]

        for i, r in enumerate(results):
            r.rank = i + 1

        return results

    def update_documents(
        self, documents: List[str], metadatas: Optional[List[dict]] = None
    ):
        """更新文档列表"""
        self.documents = documents
        self.metadatas = metadatas or [{"index": i} for i in range(len(documents))]
        self._build_index()
