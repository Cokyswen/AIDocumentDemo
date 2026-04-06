"""
文档管理器的单元测试
"""

import pytest
from pathlib import Path
import tempfile
import os

from core.indexing import DocumentProcessor, DocumentParser
from core.document_manager import DocumentManager


class TestDocumentProcessor:
    """文档处理器测试类"""

    def test_processor_initialization(self):
        """测试处理器初始化"""
        processor = DocumentProcessor(chunk_size=200, overlap=30)
        assert processor is not None
        assert processor.chunker.chunk_size == 200
        assert processor.chunker.overlap == 30


class TestDocumentParser:
    """文档解析器测试类"""

    def test_parser_initialization(self):
        """测试解析器初始化"""
        parser = DocumentParser()
        assert parser is not None
        assert len(parser.parsers) >= 3

    def test_text_parser(self):
        """测试文本文件解析"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("测试文本内容")
            temp_path = f.name

        parser = DocumentParser()
        content = parser.parse(Path(temp_path))
        assert "测试文本" in content

        os.unlink(temp_path)


class TestDocumentManager:
    """文档管理器测试类"""

    def test_manager_initialization(self):
        """测试管理器初始化"""
        config = {
            "document": {
                "processing": {"chunk_size": 200, "overlap": 30},
                "supported_extensions": [".txt", ".md"],
            }
        }
        manager = DocumentManager(config)
        assert manager is not None

    def test_is_supported(self):
        """测试文件类型支持"""
        config = {
            "document": {"supported_extensions": [".txt", ".md", ".pdf", ".docx"]}
        }
        manager = DocumentManager(config)

        assert manager.is_supported(Path("test.txt"))
        assert manager.is_supported(Path("test.md"))
        assert not manager.is_supported(Path("test.xyz"))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
