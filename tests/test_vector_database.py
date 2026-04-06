"""
向量数据库的单元测试
"""

import pytest
import tempfile
import shutil

from core.retrieval import VectorStore


@pytest.fixture
def temp_vector_db():
    """创建临时向量数据库"""
    db_path = tempfile.mkdtemp()
    yield VectorStore(db_path, "test_collection")
    shutil.rmtree(db_path, ignore_errors=True)


class TestVectorDatabase:
    """向量数据库测试类"""

    def test_initialization(self, temp_vector_db):
        """测试初始化"""
        assert temp_vector_db.collection is not None
        assert temp_vector_db.collection_name == "test_collection"

    def test_add(self, temp_vector_db):
        """测试添加文档"""
        docs = ["第一个文档", "第二个文档"]
        metas = [{"source": "test1"}, {"source": "test2"}]

        doc_ids = temp_vector_db.add(docs, metas)

        assert len(doc_ids) == 2
        assert all(doc_ids)

    def test_search(self, temp_vector_db):
        """测试搜索"""
        docs = ["Python编程语言", "JavaScript Web开发"]
        temp_vector_db.add(docs)

        results = temp_vector_db.search("Python", n_results=2)

        assert len(results) >= 1

    def test_get_info(self, temp_vector_db):
        """测试获取信息"""
        temp_vector_db.add(["测试文档"])

        info = temp_vector_db.get_info()

        assert info["name"] == "test_collection"
        assert info["count"] >= 1

    def test_delete(self, temp_vector_db):
        """测试删除"""
        docs = ["要删除的文档"]
        ids = temp_vector_db.add(docs)

        result = temp_vector_db.delete(ids)

        assert result is True

    def test_search_empty_query(self, temp_vector_db):
        """测试空查询"""
        results = temp_vector_db.search("", n_results=5)
        assert results == []

    def test_count(self, temp_vector_db):
        """测试文档计数"""
        initial = temp_vector_db.count()
        temp_vector_db.add(["新文档"])
        assert temp_vector_db.count() == initial + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
