"""
向量存储 - ChromaDB 封装
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid

import chromadb
from chromadb.config import Settings


@dataclass
class RetrievalResult:
    """检索结果"""

    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
            "rank": self.rank,
        }


class EmbeddingFunction:
    """嵌入函数封装"""

    FALLBACK_MODELS = [
        "paraphrase-multilingual-MiniLM-L12-v2",
        "all-MiniLM-L6-v2",
    ]

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """懒加载模型，带有备用模型降级机制"""
        if self._model is None:
            models_to_try = [self.model_name] + self.FALLBACK_MODELS
            tried_models = set()

            for model_name in models_to_try:
                if model_name in tried_models:
                    continue
                tried_models.add(model_name)

                try:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(model_name)
                    if model_name != self.model_name:
                        logging.warning(
                            f"指定的嵌入模型 {self.model_name} 不可用，"
                            f"降级使用: {model_name}"
                        )
                    else:
                        logging.info(f"嵌入模型加载成功: {model_name}")
                    self.model_name = model_name
                    return self._model
                except ImportError:
                    logging.warning(
                        f"sentence-transformers 未安装，无法加载模型 {model_name}"
                    )
                except Exception as e:
                    logging.warning(f"嵌入模型 {model_name} 加载失败: {e}")
                    continue

            logging.error("所有嵌入模型加载失败，将使用 ChromaDB 默认嵌入")
            return None
        return self._model

    def __call__(self, input: List[str]) -> List[List[float]]:
        """生成嵌入向量 - ChromaDB 1.5.x 接口"""
        return self.embed_documents(input)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表"""
        model = self._load_model()
        if model is None:
            return None

        try:
            embeddings = model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            logging.error(f"文档嵌入生成失败: {e}")
            return None

    def embed_query(self, input) -> List[List[float]]:
        """嵌入单个查询 - ChromaDB 1.5.x 接口"""
        model = self._load_model()
        if model is None:
            return None

        try:
            if isinstance(input, list):
                input = input[0] if input else ""
            embedding = model.encode([input])
            return embedding.tolist()
        except Exception as e:
            logging.error(f"查询嵌入生成失败: {e}")
            return None


class VectorStore:
    """向量存储管理器"""

    def __init__(
        self,
        persist_dir: str,
        collection_name: str = "documents",
        embedding_model: Optional[str] = None,
    ):
        """
        初始化向量存储

        Args:
            persist_dir: 持久化目录
            collection_name: 集合名称
            embedding_model: 嵌入模型名称（支持中文的多语言模型）
        """
        self.logger = logging.getLogger(__name__)
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # 嵌入函数
        self.embedding_fn = None
        if embedding_model:
            self.embedding_fn = EmbeddingFunction(embedding_model)

        # 初始化 ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir), settings=Settings(anonymized_telemetry=False)
        )

        # 获取或创建集合
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        """获取或创建集合"""
        try:
            return self.client.get_collection(self.collection_name)
        except:
            # 创建集合，传入嵌入函数
            if self.embedding_fn:
                return self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Document store"},
                    embedding_function=self.embedding_fn,
                )
            else:
                return self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Document store"},
                )

    def add(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        添加文档

        Args:
            texts: 文档内容列表
            metadatas: 元数据列表
            ids: ID列表

        Returns:
            生成的ID列表
        """
        if not texts:
            self.logger.warning("添加文档: 文本列表为空")
            return []

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        if metadatas is None:
            metadatas = [{"index": i} for i in range(len(texts))]

        # 记录添加的文档信息
        self.logger.info(f"[向量存储] 开始添加 {len(texts)} 个文档")
        for i, (text, meta) in enumerate(zip(texts, metadatas)):
            source = meta.get("source", "unknown")
            content_preview = text[:100].replace("\n", " ")
            self.logger.debug(
                f"  文档{i + 1}: source={source}, 内容预览: {content_preview}..."
            )

        try:
            self.collection.add(documents=texts, ids=ids, metadatas=metadatas)
            self.logger.info(
                f"[向量存储] 成功添加 {len(texts)} 个文档, IDs: {[i[:8] for i in ids]}"
            )
            return ids
        except Exception as e:
            self.logger.error(f"[向量存储] 添加文档失败: {e}")
            return []

    def search(
        self, query: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """
        搜索相似文档

        Args:
            query: 查询文本
            n_results: 返回数量
            where: 元数据过滤条件

        Returns:
            RetrievalResult 列表
        """
        self.logger.info(f'[向量检索] 查询: "{query}", 请求数量: {n_results}')

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            if not results or not results.get("documents"):
                self.logger.info("[向量检索] 未找到匹配结果")
                return []

            docs = results["documents"][0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            ids = results.get("ids", [[]])[0]

            retrieval_results = []
            for i, doc in enumerate(docs):
                # 归一化距离到相似度
                score = 1.0 - distances[i] if i < len(distances) else 0.0
                meta = metadatas[i] if i < len(metadatas) else {}
                meta["id"] = ids[i] if i < len(ids) else None

                result = RetrievalResult(
                    content=doc, score=max(0.0, score), metadata=meta, rank=i + 1
                )
                retrieval_results.append(result)

                # 记录检索结果
                source = meta.get("source", "unknown")
                content_preview = doc[:60].replace("\n", " ")
                self.logger.debug(
                    f"  结果{i + 1}: score={score:.3f}, source={source}, 内容: {content_preview}..."
                )

            self.logger.info(f"[向量检索] 向量搜索返回 {len(retrieval_results)} 个结果")

            # 如果向量检索结果分数都很低，使用关键词搜索补充
            if all(r.score < 0.1 for r in retrieval_results):
                self.logger.info("[向量检索] 向量检索分数较低，启用关键词搜索")
                keyword_results = self._keyword_search(query, n_results * 2)
                if keyword_results:
                    self.logger.info(
                        f"[向量检索] 关键词搜索返回 {len(keyword_results)} 个结果"
                    )
                    for kr in keyword_results:
                        existing = next(
                            (r for r in retrieval_results if r.content == kr.content),
                            None,
                        )
                        if existing:
                            if kr.score > existing.score:
                                existing.score = kr.score
                                self.logger.debug(
                                    f"  [关键词] 更新分数: {kr.score:.3f}, "
                                    f"source={kr.metadata.get('source', 'unknown')}"
                                )
                        else:
                            retrieval_results.append(kr)
                            self.logger.debug(
                                f"  [关键词] 新增结果: score={kr.score:.3f}, "
                                f"source={kr.metadata.get('source', 'unknown')}"
                            )
                    retrieval_results.sort(key=lambda x: x.score, reverse=True)
                    for i, r in enumerate(retrieval_results[:n_results]):
                        r.rank = i + 1

            final_results = retrieval_results[:n_results]
            self.logger.info(f"[向量检索] 最终返回 {len(final_results)} 个结果")
            return final_results

        except Exception as e:
            self.logger.error(f"[向量检索] 搜索失败: {e}")
            return []

    def _keyword_search(self, query: str, n_results: int = 5) -> List[RetrievalResult]:
        """简单的关键词搜索"""
        try:
            keywords = self._extract_keywords(query)
            self.logger.debug(f"[关键词搜索] 提取关键词: {keywords}")

            if not keywords:
                return []

            all_docs = self.collection.get(include=["documents", "metadatas"])
            if not all_docs.get("documents"):
                return []

            scored_docs = []
            seen = set()
            for i, doc in enumerate(all_docs["documents"]):
                doc_key = doc[:100]
                if doc_key in seen:
                    continue
                seen.add(doc_key)

                meta = (
                    all_docs["metadatas"][i] if i < len(all_docs["metadatas"]) else {}
                )

                doc_lower = doc.lower()
                source_lower = meta.get("source", "").lower()

                matches = sum(1 for kw in keywords if kw.lower() in doc_lower)
                source_matches = sum(1 for kw in keywords if kw.lower() in source_lower)

                if matches > 0 or source_matches > 0:
                    total_matches = matches + source_matches * 2
                    score = min(total_matches / len(keywords), 1.0)
                    scored_docs.append(
                        RetrievalResult(content=doc, score=score, metadata=meta, rank=0)
                    )

            scored_docs.sort(key=lambda x: x.score, reverse=True)
            return scored_docs[:n_results]

        except Exception as e:
            self.logger.warning(f"[关键词搜索] 搜索失败: {e}")
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词 - 支持中英文，使用bigram分词"""
        import re

        english_words = re.findall(r"[a-zA-Z0-9_]+", text)

        chinese_text = re.sub(r"[a-zA-Z0-9_\s]", "", text)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", chinese_text)

        chinese_bigrams = []
        for i in range(len(chinese_chars) - 1):
            bigram = chinese_chars[i] + chinese_chars[i + 1]
            chinese_bigrams.append(bigram)

        chinese_phrases = re.findall(r"[\u4e00-\u9fff]{2,}", chinese_text)

        all_words = english_words + chinese_bigrams + chinese_phrases
        filtered = [w for w in all_words if len(w) >= 2]

        return list(set(filtered))

    def delete(self, ids: List[str]) -> bool:
        """删除文档"""
        try:
            self.collection.delete(ids=ids)
            return True
        except Exception as e:
            self.logger.error(f"删除失败: {e}")
            return False

    def clear(self) -> None:
        """清空集合"""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self._get_or_create_collection()
        except Exception as e:
            self.logger.error(f"清空集合失败: {e}")

    def count(self) -> int:
        """获取文档数量"""
        return self.collection.count()

    def get_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        return {
            "name": self.collection_name,
            "count": self.count(),
            "persist_dir": str(self.persist_dir),
        }

    def close(self) -> None:
        """关闭连接"""
        try:
            self.client = None
            self.collection = None
        except Exception:
            pass
