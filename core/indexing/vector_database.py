"""
向量数据库 - 使用检索模块
"""

from core.retrieval import VectorStore, RetrievalResult, Retriever

__all__ = ["VectorStore", "RetrievalResult", "Retriever"]


def create_vector_database(config) -> VectorStore:
    """
    创建向量数据库实例

    Args:
        config: 配置字典

    Returns:
        VectorStore 实例
    """
    vector_config = config.get("vector_db", {}).get("chroma", {})

    persist_directory = vector_config.get("persist_directory", "data/chroma_db")
    collection_name = vector_config.get("collection_name", "document_collection")

    # 获取嵌入模型配置
    embedding_model = vector_config.get("embedding_model", None)

    return VectorStore(persist_directory, collection_name, embedding_model)
