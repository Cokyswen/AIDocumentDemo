"""
异常处理管理器 - 负责全局异常捕获、错误处理和用户友好的错误显示
"""

import logging
import sys
import traceback
import time
from typing import Dict, Any, Optional, Callable, List
from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QApplication


class ErrorSeverity(Enum):
    """错误严重程度枚举"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorType(Enum):
    """错误类型枚举"""

    NETWORK_ERROR = "network_error"
    FILE_ERROR = "file_error"
    CONFIG_ERROR = "config_error"
    AI_SERVICE_ERROR = "ai_service_error"
    DATABASE_ERROR = "database_error"
    UI_ERROR = "ui_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


class ErrorInfo:
    """错误信息类"""

    def __init__(
        self,
        error_type: ErrorType,
        error_message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):

        self.error_type = error_type
        self.error_message = error_message
        self.severity = severity
        self.details = details
        self.context = context or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "type": self.error_type.value,
            "message": self.error_message,
            "severity": self.severity.value,
            "details": self.details,
            "context": self.context,
            "timestamp": self.timestamp,
        }


class ErrorHandler(QObject):
    """异常处理管理器"""

    # 信号定义
    error_occurred = Signal(ErrorInfo)  # 错误发生信号
    error_resolved = Signal(ErrorInfo)  # 错误解决信号
    error_logged = Signal(ErrorInfo)  # 错误记录信号

    def __init__(self, show_user_alerts: bool = True):
        """
        初始化错误处理器

        Args:
            show_user_alerts: 是否显示用户警告
        """
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.show_user_alerts = show_user_alerts

        # 错误记录
        self.error_log: List[ErrorInfo] = []
        self.max_log_size = 1000  # 最大错误日志数量

        # 错误恢复策略
        self.recovery_strategies: Dict[ErrorType, Callable] = {}

        # 安装全局异常捕获
        self._install_global_exception_handler()

        self.logger.info("异常处理管理器初始化完成")

    def _install_global_exception_handler(self) -> None:
        """安装全局异常处理器"""

        def global_exception_handler(exctype, value, tb):
            """全局异常处理函数"""
            # 获取错误详情
            error_details = "".join(traceback.format_exception(exctype, value, tb))

            # 确定错误类型
            error_type = self._determine_error_type(exctype, value)

            # 创建错误信息
            error_info = ErrorInfo(
                error_type=error_type,
                error_message=str(value),
                details=error_details,
                severity=ErrorSeverity.CRITICAL,
            )

            # 处理错误
            self.handle_error(error_info)

            # 记录到标准错误流
            print(f"未捕获的异常:\n{error_details}", file=sys.stderr)

        # 设置全局异常处理器
        sys.excepthook = global_exception_handler

    def _determine_error_type(self, exctype, value) -> ErrorType:
        """确定错误类型"""
        error_str = str(exctype).lower()
        error_msg = str(value).lower()

        # 网络相关错误
        if any(
            keyword in error_str or keyword in error_msg
            for keyword in ["connection", "network", "timeout", "socket"]
        ):
            return ErrorType.NETWORK_ERROR

        # 文件相关错误
        elif any(
            keyword in error_str or keyword in error_msg
            for keyword in ["file", "directory", "path", "io", "permission"]
        ):
            return ErrorType.FILE_ERROR

        # 配置相关错误
        elif any(
            keyword in error_str or keyword in error_msg
            for keyword in ["config", "settings", "parameter"]
        ):
            return ErrorType.CONFIG_ERROR

        # 数据库相关错误
        elif any(
            keyword in error_str or keyword in error_msg
            for keyword in ["database", "connection", "sql", "query"]
        ):
            return ErrorType.DATABASE_ERROR

        # 验证相关错误
        elif any(
            keyword in error_str or keyword in error_msg
            for keyword in ["validation", "invalid", "missing", "required"]
        ):
            return ErrorType.VALIDATION_ERROR

        # AI服务相关错误
        elif any(
            keyword in error_str or error_str in error_msg
            for keyword in ["openai", "api", "key", "service"]
        ):
            return ErrorType.AI_SERVICE_ERROR

        # UI相关错误
        elif any(
            keyword in error_str or keyword in error_msg
            for keyword in ["qt", "widget", "ui", "layout"]
        ):
            return ErrorType.UI_ERROR

        else:
            return ErrorType.UNKNOWN_ERROR

    def handle_error(self, error_info: ErrorInfo) -> bool:
        """
        处理错误

        Args:
            error_info: 错误信息

        Returns:
            bool: 是否成功处理
        """
        try:
            # 记录错误
            self._log_error(error_info)

            # 发出错误信号
            self.error_occurred.emit(error_info)

            # 显示用户警告
            if self.show_user_alerts:
                self._show_user_alert(error_info)

            # 尝试恢复
            if error_info.error_type in self.recovery_strategies:
                return self._attempt_recovery(error_info)

            return True

        except Exception as e:
            self.logger.error(f"处理错误时发生异常: {e}")
            return False

    def _log_error(self, error_info: ErrorInfo) -> None:
        """记录错误"""
        # 添加到错误日志
        self.error_log.append(error_info)

        # 限制日志大小
        if len(self.error_log) > self.max_log_size:
            self.error_log.pop(0)

        # 根据严重程度记录到日志系统
        log_message = f"[{error_info.error_type.value}] {error_info.error_message}"

        if error_info.severity == ErrorSeverity.INFO:
            self.logger.info(log_message)
        elif error_info.severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        elif error_info.severity == ErrorSeverity.ERROR:
            self.logger.error(log_message)
        else:  # CRITICAL
            self.logger.critical(log_message)

        # 如果错误详细信息存在，记录详细信息
        if error_info.details:
            self.logger.debug(f"错误详情: {error_info.details}")

        # 发出错误记录信号
        self.error_logged.emit(error_info)

    def _show_user_alert(self, error_info: ErrorInfo) -> None:
        """显示用户警告"""
        try:
            # 确保在主线程中显示对话框
            def show_message():
                # 根据错误严重程度选择消息框类型
                if error_info.severity in [ErrorSeverity.INFO, ErrorSeverity.WARNING]:
                    QMessageBox.warning(
                        None, "系统警告", self._format_user_message(error_info)
                    )
                else:
                    QMessageBox.critical(
                        None, "系统错误", self._format_user_message(error_info)
                    )

            # 在主线程中执行
            QApplication.instance().postEvent(
                QApplication.instance(), lambda: show_message()
            )

        except Exception as e:
            self.logger.error(f"显示用户警告失败: {e}")

    def _format_user_message(self, error_info: ErrorInfo) -> str:
        """格式化用户友好的错误消息"""
        error_messages = {
            ErrorType.NETWORK_ERROR: "网络连接错误。请检查网络连接并重试。",
            ErrorType.FILE_ERROR: "文件操作错误。请检查文件权限和路径。",
            ErrorType.CONFIG_ERROR: "配置错误。请检查应用程序设置。",
            ErrorType.AI_SERVICE_ERROR: "AI服务错误。请检查API密钥和网络连接。",
            ErrorType.DATABASE_ERROR: "数据库错误。请检查数据库连接。",
            ErrorType.VALIDATION_ERROR: "数据验证错误。请检查输入格式。",
            ErrorType.UI_ERROR: "界面显示错误。请重启应用程序。",
            ErrorType.UNKNOWN_ERROR: "未知错误。请查看日志文件获取详情。",
        }

        base_message = error_messages.get(
            error_info.error_type, error_messages[ErrorType.UNKNOWN_ERROR]
        )

        return f"{base_message}\n\n错误详情: {error_info.error_message}"

    def _attempt_recovery(self, error_info: ErrorInfo) -> bool:
        """尝试恢复"""
        try:
            recovery_func = self.recovery_strategies.get(error_info.error_type)
            if recovery_func:
                return recovery_func(error_info)
            return False
        except Exception as e:
            self.logger.error(f"错误恢复尝试失败: {e}")
            return False

    def register_recovery_strategy(
        self, error_type: ErrorType, strategy_func: Callable
    ) -> None:
        """
        注册错误恢复策略

        Args:
            error_type: 错误类型
            strategy_func: 恢复策略函数
        """
        self.recovery_strategies[error_type] = strategy_func

    def get_error_log(self, max_entries: int = 50) -> List[Dict[str, Any]]:
        """
        获取错误日志

        Args:
            max_entries: 最大条目数

        Returns:
            List[Dict]: 错误日志
        """
        recent_errors = self.error_log[-max_entries:]
        return [error.to_dict() for error in recent_errors]

    def clear_error_log(self) -> None:
        """清空错误日志"""
        self.error_log.clear()

    def handle_network_error(
        self, error_message: str, context: Dict[str, Any] = None
    ) -> bool:
        """处理网络错误"""
        error_info = ErrorInfo(
            error_type=ErrorType.NETWORK_ERROR,
            error_message=error_message,
            severity=ErrorSeverity.ERROR,
            context=context,
        )
        return self.handle_error(error_info)

    def handle_file_error(
        self, error_message: str, context: Dict[str, Any] = None
    ) -> bool:
        """处理文件错误"""
        error_info = ErrorInfo(
            error_type=ErrorType.FILE_ERROR,
            error_message=error_message,
            severity=ErrorSeverity.ERROR,
            context=context,
        )
        return self.handle_error(error_info)

    def handle_config_error(
        self, error_message: str, context: Dict[str, Any] = None
    ) -> bool:
        """处理配置错误"""
        error_info = ErrorInfo(
            error_type=ErrorType.CONFIG_ERROR,
            error_message=error_message,
            severity=ErrorSeverity.WARNING,
            context=context,
        )
        return self.handle_error(error_info)

    def handle_ai_service_error(
        self, error_message: str, context: Dict[str, Any] = None
    ) -> bool:
        """处理AI服务错误"""
        error_info = ErrorInfo(
            error_type=ErrorType.AI_SERVICE_ERROR,
            error_message=error_message,
            severity=ErrorSeverity.ERROR,
            context=context,
        )
        return self.handle_error(error_info)

    def handle_document_parsing_error(
        self, error_message: str, context: Dict[str, Any] = None
    ) -> bool:
        """处理文档解析错误"""
        # 归为文件错误类型
        return self.handle_file_error(f"文档解析失败: {error_message}", context)


def create_error_handler(show_user_alerts: bool = True) -> ErrorHandler:
    """
    创建错误处理器实例

    Args:
        show_user_alerts: 是否显示用户警告

    Returns:
        ErrorHandler: 错误处理器实例
    """
    return ErrorHandler(show_user_alerts=show_user_alerts)


def setup_global_error_handling() -> ErrorHandler:
    """设置全局错误处理"""
    error_handler = create_error_handler()

    # 注册默认恢复策略
    error_handler.register_recovery_strategy(
        ErrorType.NETWORK_ERROR, lambda error: _retry_network_operation(error)
    )

    error_handler.register_recovery_strategy(
        ErrorType.CONFIG_ERROR, lambda error: _reset_config_to_defaults(error)
    )

    return error_handler


def _retry_network_operation(error_info: ErrorInfo) -> bool:
    """重试网络操作（示例实现）"""
    # 在实际实现中，这里可以包含重试逻辑
    import time

    max_retries = 3

    for attempt in range(max_retries):
        time.sleep(1)  # 等待1秒后重试
        # 这里应该包含重试逻辑
        # 如果成功返回True

    return False  # 重试失败


def _reset_config_to_defaults(error_info: ErrorInfo) -> bool:
    """重置配置为默认值（示例实现）"""
    # 在实际实现中，这里可以重置配置
    try:
        # 重置配置逻辑
        return True
    except Exception:
        return False
