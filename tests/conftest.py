"""
测试配置文件 - 提供测试所需的共享fixtures和配置
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import tempfile
import shutil
from unittest.mock import Mock


@pytest.fixture(scope="session")
def temp_dir():
    """创建临时目录用于测试"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # 测试结束后清理
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_config():
    """模拟配置数据"""
    return {
        "openai": {
            "api_key": "test_api_key",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "database": {
            "path": "./test_data/vector_db"
        }
    }


@pytest.fixture
def mock_document_content():
    """模拟文档内容"""
    return {
        "pdf_content": """
        这是测试PDF文档的内容。
        这是一个段落，包含一些测试文本。
        第二段落，继续测试文档内容。
        """,
        "docx_content": """
        Word文档测试内容
        包含多个段落的文本
        用于测试文档解析功能
        """,
        "txt_content": """
        TXT文件测试内容
        纯文本格式
        多行文本内容
        """
    }


@pytest.fixture
def sample_text_chunks():
    """样本文本块用于测试"""
    return [
        {
            "content": "第一段测试文本",
            "metadata": {"source": "test_doc_1", "page": 1}
        },
        {
            "content": "第二段测试文本，包含更多内容",
            "metadata": {"source": "test_doc_1", "page": 1}
        },
        {
            "content": "第三段文本，来自不同文档",
            "metadata": {"source": "test_doc_2", "page": 1}
        }
    ]


@pytest.fixture
def mock_ai_response():
    """模拟AI服务响应"""
    return {
        "success": True,
        "response": "这是一个测试回复",
        "info": {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            },
            "model": "gpt-3.5-turbo"
        }
    }


@pytest.fixture
def mock_error_handler():
    """模拟错误处理器"""
    handler = Mock()
    handler.handle_error = Mock()
    handler.handle_network_error = Mock()
    handler.handle_file_error = Mock()
    return handler


class MockAppState:
    """模拟应用状态"""
    def __init__(self):
        self.current_document_id = None
        self.current_document_name = None
        self.chat_history = []
        self.config = {}
        self.is_processing = False
        self.processing_progress = 0.0
        self.processing_stage = ""
        self.error_message = None


@pytest.fixture
def mock_app_state():
    """模拟应用状态"""
    return MockAppState()


@pytest.fixture
def test_resources_dir(temp_dir):
    """测试资源目录"""
    resources_dir = Path(temp_dir) / "test_resources"
    resources_dir.mkdir(exist_ok=True)
    
    # 创建测试文件
    test_txt = resources_dir / "test_document.txt"
    test_txt.write_text("这是一个测试文档的内容")
    
    return resources_dir


@pytest.fixture(scope="session")
def logger():
    """测试日志记录器"""
    import logging
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger("test")


# 测试装饰器
def skip_if_no_internet(func):
    """跳过需要互联网连接的测试"""
    import socket
    
    def wrapper(*args, **kwargs):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            return func(*args, **kwargs)
        except OSError:
            pytest.skip("需要互联网连接")
    
    return wrapper


def skip_if_no_module(module_name):
    """跳过缺少依赖模块的测试"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                __import__(module_name)
                return func(*args, **kwargs)
            except ImportError:
                pytest.skip(f"需要 {module_name} 模块")
        return wrapper
    return decorator