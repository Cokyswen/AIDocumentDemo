"""
AI 对话服务 - 整合检索和生成
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from core.retrieval import VectorStore, Retriever, RetrievalResult
from core.generation import ChatService, PromptBuilder


class CitationInfo:
    """引用信息"""

    def __init__(self, source: str, score: float, content_preview: str = ""):
        self.source = source
        self.score = score
        self.content_preview = content_preview

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "score": self.score,
            "content_preview": self.content_preview,
        }


class AIChatService:
    """AI 对话服务"""

    def __init__(
        self, config: Dict[str, Any], vector_store: Optional[VectorStore] = None
    ):
        """
        初始化 AI 对话服务

        Args:
            config: 配置字典
            vector_store: 向量存储实例
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.last_citations: List[CitationInfo] = []

        # 初始化向量存储和检索器
        self.vector_store = vector_store
        if vector_store:
            search_config = config.get("vector_db", {}).get("search", {})
            self.retriever = Retriever(
                vector_store, top_k=search_config.get("n_results", 5)
            )
        else:
            self.retriever = None

        # 初始化提示词构建器
        context_config = config.get("ai", {}).get("context", {})
        self.prompt_builder = PromptBuilder(
            max_context_tokens=context_config.get("max_doc_context_length", 4000)
        )

        # 初始化对话服务
        self.chat_service = ChatService(config, self.prompt_builder)

    def chat(
        self, message: str, use_context: bool = True, search_query: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        发送对话请求

        Args:
            message: 用户消息
            use_context: 是否使用文档上下文
            search_query: 搜索查询

        Returns:
            (成功与否, 回复内容, 附加信息)
        """
        context_docs = None
        self.last_citations = []

        # 获取上下文文档
        if use_context and self.retriever:
            try:
                query = search_query if search_query else message
                results = self.retriever.retrieve(query)
                if results:
                    context_docs = [r.content for r in results]

                    # 保存引用信息
                    for r in results:
                        source = r.metadata.get("source", "未知来源")
                        citation = CitationInfo(
                            source=source,
                            score=r.score,
                            content_preview=r.content[:200] + "..."
                            if len(r.content) > 200
                            else r.content,
                        )
                        self.last_citations.append(citation)

                    self.logger.info(f"检索到 {len(context_docs)} 个相关文档")
            except Exception as e:
                self.logger.warning(f"文档检索失败: {e}")

        # 发送对话请求
        success, response, info = self.chat_service.chat(
            message, context_docs, use_context
        )

        # 在附加信息中添加引用
        if success and self.last_citations:
            info["citations"] = [c.to_dict() for c in self.last_citations]

        return success, response, info

    def stream_chat(self, message: str, use_context: bool = True):
        """
        流式对话

        Args:
            message: 用户消息
            use_context: 是否使用上下文

        Yields:
            文本片段或字典（包含引用信息）
        """
        context_docs = None
        self.last_citations = []

        if use_context and self.retriever:
            try:
                results = self.retriever.retrieve(message)
                if results:
                    context_docs = [r.content for r in results]

                    # 保存引用信息
                    for r in results:
                        source = r.metadata.get("source", "未知来源")
                        citation = CitationInfo(
                            source=source,
                            score=r.score,
                            content_preview=r.content[:200] + "..."
                            if len(r.content) > 200
                            else r.content,
                        )
                        self.last_citations.append(citation)
            except Exception as e:
                self.logger.warning(f"文档检索失败: {e}")

        if self.last_citations:
            yield {
                "type": "citations",
                "citations": [c.to_dict() for c in self.last_citations],
            }

        try:
            for content in self.chat_service.stream_chat(message, context_docs):
                if isinstance(content, str):
                    yield {"type": "chunk", "content": content}
                elif isinstance(content, dict):
                    yield content
                else:
                    yield {"type": "chunk", "content": str(content)}
            yield {"type": "done", "content": ""}
        except Exception as e:
            self.logger.error(f"流式对话失败: {e}")
            yield {"type": "error", "content": str(e)}

    def get_citations(self) -> List[CitationInfo]:
        """获取最后一次回复的引用信息"""
        return self.last_citations

    def validate(self) -> bool:
        """验证服务是否可用"""
        return self.chat_service.validate()

    def clear_history(self):
        """清空对话历史"""
        self.chat_service.clear_history()


def create_ai_chat_service(
    config: Dict[str, Any], vector_store: Optional[VectorStore] = None
) -> AIChatService:
    """创建 AI 对话服务"""
    return AIChatService(config, vector_store)
