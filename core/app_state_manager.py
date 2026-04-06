"""
应用状态管理类 - 负责管理整个应用的状态和数据流
"""

import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

# 尝试导入数据流管理器
try:
    from .data_flow_manager import ProcessingStage
except ImportError:
    # 如果没有data_flow_manager，定义基础枚举
    from enum import Enum

    class ProcessingStage(Enum):
        IDLE = "idle"
        DOCUMENT_PARSING = "document_parsing"
        TEXT_CHUNKING = "text_chunking"
        VECTORING = "vectoring"
        STORING = "storing"
        SEARCHING = "searching"
        CHAT_PROCESSING = "chat_processing"
        COMPLETED = "completed"
        ERROR = "error"


try:
    from .error_handler import ErrorHandler, ErrorType, ErrorSeverity, ErrorInfo
except ImportError:
    # 如果没有error_handler，定义基础枚举和类
    from enum import Enum
    from typing import Dict, Any, Optional

    class ErrorType(Enum):
        NETWORK_ERROR = "network_error"
        FILE_ERROR = "file_error"
        CONFIG_ERROR = "config_error"
        AI_SERVICE_ERROR = "ai_service_error"
        DATABASE_ERROR = "database_error"
        UI_ERROR = "ui_error"
        VALIDATION_ERROR = "validation_error"
        UNKNOWN_ERROR = "unknown_error"

    class ErrorSeverity(Enum):
        INFO = "info"
        WARNING = "warning"
        ERROR = "error"
        CRITICAL = "critical"

    class ErrorInfo:
        def __init__(
            self, error_type, error_message, severity=None, details=None, context=None
        ):
            self.error_type = error_type
            self.error_message = error_message
            self.details = details
            self.context = context

    class ErrorHandler(QObject):
        def __init__(self):
            super().__init__()
            self.logger = logging.getLogger(__name__)


from core.config_manager import ConfigManager
from core.document_manager import DocumentManager
from core.indexing.vector_database import VectorStore
from core.ai_chat import AIChatService


@dataclass
class AppState:
    """应用状态数据结构"""

    current_document_id: Optional[str] = None
    current_document_name: Optional[str] = None
    chat_history: List[Dict] = None
    config: Dict[str, Any] = None
    is_processing: bool = False
    processing_progress: float = 0.0
    processing_stage: str = ""
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.chat_history is None:
            self.chat_history = []
        if self.config is None:
            self.config = {}


class AppStateManager(QObject):
    """应用状态管理器"""

    # 信号定义
    state_changed = Signal(dict)  # 状态变更信号
    config_changed = Signal(dict)  # 配置变更信号
    document_processed = Signal(dict)  # 文档处理完成信号
    chat_message_added = Signal(dict)  # 聊天消息添加信号
    error_occurred = Signal(str)  # 错误发生信号

    # 新增信号：高级错误处理信号
    error_info_occurred = Signal(object)  # 错误信息信号
    processing_started = Signal(str)  # 处理开始信号
    processing_progress = Signal(float, str)  # 处理进度信号

    def __init__(
        self,
        config_manager: ConfigManager,
        document_manager: DocumentManager,
        vector_database: VectorStore,
        error_handler: Optional[ErrorHandler] = None,
    ):
        """
        初始化应用状态管理器

        Args:
            config_manager: 配置管理器
            document_manager: 文档管理器
            vector_database: 向量数据库
        """
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.document_manager = document_manager
        self.vector_database = vector_database

        # AI聊天服务（延迟初始化）
        self.ai_chat_service: Optional[AIChatService] = None

        # 错误处理器
        self.error_handler = error_handler if error_handler else ErrorHandler()

        # 连接错误处理器信号
        self.error_handler.error_occurred.connect(self._handle_error_signal)

        # 应用状态
        self.state = AppState()

        # 初始化配置
        self._initialize_config()

        # 互斥锁
        self._lock = threading.Lock()

        self.logger.info("应用状态管理器初始化完成")

    def _initialize_config(self) -> None:
        """初始化配置"""
        try:
            config = self.config_manager.get_config()
            self.state.config = config

            # 初始化AI聊天服务
            self.ai_chat_service = AIChatService(config)

            self.logger.info("配置初始化完成")

        except Exception as e:
            self.logger.error(f"配置初始化失败: {e}")
            self._emit_error(f"配置初始化失败: {e}")

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新配置

        Args:
            new_config: 新配置

        Returns:
            bool: 更新是否成功
        """
        with self._lock:
            try:
                # 保存配置
                if not self.config_manager.update_config(new_config):
                    raise Exception("配置管理器保存失败")

                # 更新状态
                self.state.config = new_config

                # 重新初始化AI服务
                self.ai_chat_service = AIChatService(new_config)

                # 发出配置变更信号
                self.config_changed.emit(new_config)
                self.state_changed.emit({"type": "config_updated"})

                self.logger.info("配置更新成功")
                return True

            except Exception as e:
                self.logger.error(f"配置更新失败: {e}")
                self._emit_error(f"配置更新失败: {e}")
                return False

    def process_document(self, file_path: str) -> bool:
        """
        处理文档

        Args:
            file_path: 文档文件路径

        Returns:
            bool: 处理是否成功
        """

        def _process():
            try:
                # 更新处理状态
                self._update_state(
                    {"is_processing": True, "processing_stage": "开始处理文档"}
                )

                # 解析文档
                self._update_state(
                    {"processing_stage": "解析文档内容", "processing_progress": 0.3}
                )
                success, documents, info = self.document_manager.process(file_path)

                if not success:
                    raise Exception(f"文档解析失败: {info}")

                # 向量化并存储
                self._update_state(
                    {"processing_stage": "向量化文档", "processing_progress": 0.6}
                )
                if documents:
                    texts = [d["content"] for d in documents]
                    metadatas = [d["metadata"] for d in documents]
                    self.vector_database.add(texts, metadatas)

                # 更新状态
                self._update_state(
                    {
                        "is_processing": False,
                        "processing_progress": 1.0,
                        "processing_stage": "文档处理完成",
                        "current_document_id": info.get("document_id"),
                        "current_document_name": info.get("document_name"),
                    }
                )

                # 发出文档处理完成信号
                self.document_processed.emit(
                    {
                        "document_id": info.get("document_id"),
                        "document_name": info.get("document_name"),
                        "chunk_count": len(documents),
                        "file_size": info.get("file_size", 0),
                    }
                )

                self.logger.info(f"文档处理完成: {file_path}")
                return True

            except Exception as e:
                self.logger.error(f"文档处理失败: {e}")
                self._emit_error(f"文档处理失败: {e}")
                self._update_state({"is_processing": False, "error_message": str(e)})
                return False

        # 在新线程中处理
        thread = threading.Thread(target=_process, daemon=True)
        thread.start()
        return True

    def send_chat_message(self, message: str, use_context: bool = True) -> bool:
        """
        发送聊天消息

        Args:
            message: 消息内容
            use_context: 是否使用上下文

        Returns:
            bool: 发送是否成功
        """
        if not self.ai_chat_service:
            self._emit_error("AI服务未初始化")
            return False

        def _chat():
            try:
                # 添加用户消息到历史
                self.state.chat_history.append(
                    {
                        "role": "user",
                        "content": message,
                        "timestamp": self._get_timestamp(),
                    }
                )

                # 构建上下文
                context = ""
                if use_context and self.state.current_document_id:
                    try:
                        # 从向量数据库检索相关文档
                        success, results, _ = self.vector_database.search(
                            message, top_k=3
                        )
                        if success and results:
                            context = "\n相关文档内容:\n" + "\n".join(
                                [
                                    f"- {res.get('content', '')[:200]}..."
                                    for res in results
                                ]
                            )
                    except Exception as e:
                        self.logger.warning(f"上下文检索失败: {e}")

                # 发送到AI服务
                success, response, info = self.ai_chat_service.chat(message, context)

                if success:
                    # 添加AI回复到历史
                    self.state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": response,
                            "timestamp": self._get_timestamp(),
                            "context_used": bool(context),
                        }
                    )

                    # 发出消息添加信号
                    self.chat_message_added.emit(
                        {
                            "role": "assistant",
                            "content": response,
                            "timestamp": self._get_timestamp(),
                            "token_usage": info.get("usage", {}),
                        }
                    )

                    self.logger.info(
                        f"AI回复完成，使用Token: {info.get('usage', {}).get('total_tokens', 0)}"
                    )

                else:
                    self._emit_error(f"AI回复失败: {response}")

                # 更新状态
                self.state_changed.emit({"type": "chat_updated"})

            except Exception as e:
                self.logger.error(f"发送聊天消息失败: {e}")
                self._emit_error(f"发送聊天消息失败: {e}")

        # 在新线程中处理
        thread = threading.Thread(target=_chat, daemon=True)
        thread.start()
        return True

    def clear_chat_history(self) -> None:
        """清空聊天历史"""
        self.state.chat_history.clear()
        if self.ai_chat_service:
            self.ai_chat_service.clear_conversation()

        self.state_changed.emit({"type": "chat_cleared"})
        self.logger.info("聊天历史已清空")

    def get_document_list(self) -> List[Dict[str, Any]]:
        """
        获取文档列表

        Returns:
            List[Dict]: 文档列表
        """
        try:
            # 从向量数据库获取文档列表
            success, documents, _ = self.vector_database.list_documents()
            if success:
                return documents
            return []
        except Exception as e:
            self.logger.error(f"获取文档列表失败: {e}")
            return []

    def search_documents(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索文档

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            List[Dict]: 搜索结果
        """
        try:
            success, results, _ = self.vector_database.search(query, top_k=top_k)
            if success:
                return results
            return []
        except Exception as e:
            self.logger.error(f"搜索文档失败: {e}")
            return []

    def delete_document(self, document_id: str) -> bool:
        """
        删除文档

        Args:
            document_id: 文档ID

        Returns:
            bool: 删除是否成功
        """
        try:
            success = self.vector_database.delete_document(document_id)

            # 如果删除的是当前文档，清空当前文档状态
            if success and self.state.current_document_id == document_id:
                self._update_state(
                    {"current_document_id": None, "current_document_name": None}
                )

            return success

        except Exception as e:
            self.logger.error(f"删除文档失败: {e}")
            self._emit_error(f"删除文档失败: {e}")
        return False

    def _emit_error(
        self, error_message: str, error_type: ErrorType = ErrorType.UNKNOWN_ERROR
    ) -> None:
        """
        发出错误信号

        Args:
            error_message: 错误消息
            error_type: 错误类型
        """
        self.error_occurred.emit(error_message)
        self._update_state({"error_message": error_message})

        # 使用错误处理器记录错误
        error_info = ErrorInfo(
            error_type=error_type,
            error_message=error_message,
            severity=ErrorSeverity.ERROR,
        )
        self.error_info_occurred.emit(error_info)

        # 调用错误处理器
        self.error_handler.handle_error(error_info)

    def _handle_error_signal(self, error_info: ErrorInfo) -> None:
        """处理来自错误处理器的错误信号"""
        # 更新状态
        self._update_state(
            {
                "error_message": f"[{error_info.error_type.value}] {error_info.error_message}"
            }
        )

        # 根据错误类型采取不同策略
        if error_info.error_type == ErrorType.AI_SERVICE_ERROR:
            self._handle_ai_service_error(error_info)
        elif error_info.error_type == ErrorType.CONFIG_ERROR:
            self._handle_config_error(error_info)
        elif error_info.error_type == ErrorType.NETWORK_ERROR:
            self._handle_network_error(error_info)

    def _handle_ai_service_error(self, error_info: ErrorInfo) -> None:
        """处理AI服务错误"""
        # 重置AI服务连接
        if self.ai_chat_service:
            try:
                self.ai_chat_service.reconnect()
            except Exception as e:
                self.logger.warning(f"AI服务重连失败: {e}")

    def _handle_config_error(self, error_info: ErrorInfo) -> None:
        """处理配置错误"""
        # 尝试重新加载配置
        try:
            config = self.config_manager.load_config()
            self.state.config = config
            self.logger.info("配置重新加载成功")
        except Exception as e:
            self.logger.error(f"配置重新加载失败: {e}")

    def _handle_network_error(self, error_info: ErrorInfo) -> None:
        """处理网络错误"""
        # 记录网络状态
        self.logger.warning("检测到网络错误，将在下次操作时重试")

    def set_current_document(self, file_info: Dict[str, Any]) -> None:
        """
        设置当前文档

        Args:
            file_info: 文件信息字典
        """
        self._update_state(
            {
                "current_document_id": file_info.get("file_path", ""),
                "current_document_name": file_info.get("file_name", ""),
            }
        )

    def _update_state(self, updates: Dict[str, Any]) -> None:
        """
        更新应用状态

        Args:
            updates: 状态更新字典
        """
        with self._lock:
            for key, value in updates.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
            self.state_changed.emit(updates)

    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime

        return datetime.now().strftime("%H:%M:%S")

    # 属性访问方法
    @property
    def current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self.state.config

    @property
    def current_chat_history(self) -> List[Dict]:
        """获取当前聊天历史"""
        return self.state.chat_history

    @property
    def current_document(self) -> Optional[Dict[str, str]]:
        """获取当前文档信息"""
        if self.state.current_document_id:
            return {
                "id": self.state.current_document_id,
                "name": self.state.current_document_name,
            }
        return None
