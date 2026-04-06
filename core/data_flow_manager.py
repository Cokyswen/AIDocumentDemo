"""
数据流管理器 - 负责管理应用程序内部的数据流动和处理流程
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QObject, Signal


class ProcessingStage(Enum):
    """处理阶段枚举"""

    IDLE = "idle"
    DOCUMENT_PARSING = "document_parsing"
    TEXT_CHUNKING = "text_chunking"
    VECTORING = "vectoring"
    STORING = "storing"
    SEARCHING = "searching"
    CHAT_PROCESSING = "chat_processing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class DataFlowState:
    """数据流状态"""

    current_stage: ProcessingStage = ProcessingStage.IDLE
    progress: float = 0.0  # 0.0 - 1.0
    current_document: Optional[Dict] = None
    active_queries: List[str] = field(default_factory=list)
    processing_stats: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class DataFlowManager(QObject):
    """数据流管理器"""

    # 信号定义
    flow_state_changed = Signal(dict)  # 数据流状态变更
    processing_started = Signal(str)  # 处理开始
    processing_progress = Signal(float, str)  # 处理进度
    processing_completed = Signal(dict)  # 处理完成
    processing_error = Signal(str, str)  # 处理错误

    def __init__(self):
        """初始化数据流管理器"""
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.state = DataFlowState()
        self._lock = threading.Lock()

        # 进度回调字典
        self._progress_callbacks: Dict[ProcessingStage, Callable] = {}

        self.logger.info("数据流管理器初始化完成")

    def start_document_processing(self, file_info: Dict[str, Any]) -> bool:
        """
        开始文档处理流程

        Args:
            file_info: 文件信息

        Returns:
            bool: 是否成功启动
        """
        with self._lock:
            if self.state.current_stage != ProcessingStage.IDLE:
                self.logger.warning("已有任务正在处理中")
                return False

            self.state.current_document = file_info
            self._set_stage(ProcessingStage.DOCUMENT_PARSING, 0.0)

            self.processing_started.emit(
                f"开始处理文档: {file_info.get('file_name', '未知')}"
            )

            return True

    def update_document_processing_stage(
        self, stage: ProcessingStage, progress: float
    ) -> None:
        """
        更新文档处理阶段

        Args:
            stage: 处理阶段
            progress: 处理进度 (0.0-1.0)
        """
        with self._lock:
            self.state.progress = progress
            self.state.current_stage = stage

            # 更新处理统计
            if stage.value not in self.state.processing_stats:
                self.state.processing_stats[stage.value] = {
                    "start_time": time.time(),
                    "count": 0,
                }

            self.state.processing_stats[stage.value]["count"] += 1

            # 发出进度信号
            self.processing_progress.emit(progress, stage.value)
            self.flow_state_changed.emit(
                {
                    "stage": stage.value,
                    "progress": progress,
                    "current_document": self.state.current_document,
                }
            )

    def complete_document_processing(self, result: Dict[str, Any]) -> None:
        """
        完成文档处理

        Args:
            result: 处理结果
        """
        with self._lock:
            self._set_stage(ProcessingStage.COMPLETED, 1.0)

            # 记录处理时间
            if self.state.current_document:
                result["processing_time"] = (
                    time.time()
                    - self.state.processing_stats.get(
                        ProcessingStage.DOCUMENT_PARSING.value, {}
                    ).get("start_time", time.time())
                )

            self.processing_completed.emit(result)

            # 重置状态
            self.state.current_document = None

    def handle_document_processing_error(
        self, error_message: str, stage: ProcessingStage
    ) -> None:
        """
        处理文档处理错误

        Args:
            error_message: 错误消息
            stage: 发生错误的阶段
        """
        with self._lock:
            self.state.error_message = error_message
            self._set_stage(ProcessingStage.ERROR, 0.0)

            self.processing_error.emit(stage.value, error_message)
            self.logger.error(f"文档处理阶段 {stage.value} 发生错误: {error_message}")

    def start_chat_processing(self, query: str) -> bool:
        """
        开始聊天处理流程

        Args:
            query: 用户查询

        Returns:
            bool: 是否成功启动
        """
        with self._lock:
            self.state.active_queries.append(query)
            self._set_stage(ProcessingStage.CHAT_PROCESSING, 0.0)

            self.logger.info(f"开始处理聊天查询: {query[:50]}...")
            return True

    def complete_chat_processing(self, query: str, response: Dict[str, Any]) -> None:
        """
        完成聊天处理

        Args:
            query: 原查询
            response: AI回复
        """
        with self._lock:
            if query in self.state.active_queries:
                self.state.active_queries.remove(query)

            if not self.state.active_queries:
                self._set_stage(ProcessingStage.IDLE, 0.0)

    def handle_chat_processing_error(self, query: str, error_message: str) -> None:
        """
        处理聊天处理错误

        Args:
            query: 原查询
            error_message: 错误消息
        """
        with self._lock:
            if query in self.state.active_queries:
                self.state.active_queries.remove(query)

            self.state.error_message = error_message
            self._set_stage(ProcessingStage.ERROR, 0.0)

            self.logger.error(f"聊天处理发生错误 (查询: {query}): {error_message}")

    def register_progress_callback(
        self, stage: ProcessingStage, callback: Callable
    ) -> None:
        """
        注册进度回调函数

        Args:
            stage: 处理阶段
            callback: 回调函数
        """
        self._progress_callbacks[stage] = callback

    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        获取处理统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._lock:
            stats = {
                "current_stage": self.state.current_stage.value,
                "progress": self.state.progress,
                "active_queries": len(self.state.active_queries),
                "processing_stats": self.state.processing_stats.copy(),
            }

            # 计算各阶段的平均时间
            for stage, data in stats["processing_stats"].items():
                if data.get("count", 0) > 0:
                    total_time = (
                        time.time() - data["start_time"]
                        if data.get("start_time")
                        else 0
                    )
                    data["average_time"] = total_time / data["count"]

            return stats

    def clear_error(self) -> None:
        """清除错误状态"""
        with self._lock:
            if self.state.current_stage == ProcessingStage.ERROR:
                self.state.error_message = None
                self._set_stage(ProcessingStage.IDLE, 0.0)

    def is_processing(self) -> bool:
        """
        检查是否有任务正在处理

        Returns:
            bool: 是否正在处理
        """
        with self._lock:
            return (
                self.state.current_stage
                not in [
                    ProcessingStage.IDLE,
                    ProcessingStage.COMPLETED,
                    ProcessingStage.ERROR,
                ]
                or len(self.state.active_queries) > 0
            )

    def _set_stage(self, stage: ProcessingStage, progress: float) -> None:
        """
        设置处理阶段和进度

        Args:
            stage: 新阶段
            progress: 进度值
        """
        self.state.current_stage = stage
        self.state.progress = max(0.0, min(1.0, progress))

        # 调用注册的回调函数
        if stage in self._progress_callbacks:
            try:
                self._progress_callbacks[stage](progress)
            except Exception as e:
                self.logger.error(f"进度回调执行失败: {e}")

        # 发出状态变更信号
        self.flow_state_changed.emit(
            {
                "stage": stage.value,
                "progress": progress,
                "is_processing": self.is_processing(),
            }
        )
