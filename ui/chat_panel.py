"""
AI对话面板 - 中间对话交互区域
"""

import logging
import datetime
from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QScrollArea,
    QLabel,
    QFrame,
    QSizePolicy,
    QMessageBox,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread

from core.config_manager import ConfigManager
from core.ai_chat import AIChatService


class CitationWidget(QFrame):
    """引用来源组件"""

    def __init__(self, citations: list):
        """
        初始化引用组件

        Args:
            citations: 引用列表 [{source, score, content_preview}, ...]
        """
        super().__init__()
        self.citations = citations
        self._create_ui()

    def _create_ui(self) -> None:
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        header = QLabel("📚 引用来源")
        header.setStyleSheet("font-weight: bold; font-size: 11px; color: #666;")
        layout.addWidget(header)

        for i, citation in enumerate(self.citations, 1):
            citation_frame = QFrame()
            citation_frame.setStyleSheet("""
                QFrame {
                    background-color: #e8f4ea;
                    border-radius: 5px;
                    padding: 5px;
                    margin: 2px;
                }
            """)
            citation_layout = QVBoxLayout(citation_frame)
            citation_layout.setContentsMargins(8, 5, 8, 5)
            citation_layout.setSpacing(2)

            source_text = citation.get("source", "未知来源")
            score_text = citation.get("score", 0)
            preview_text = citation.get("content_preview", "")

            source_label = QLabel(f"[{i}] {source_text} (相关性: {score_text:.2f})")
            source_label.setStyleSheet(
                "font-size: 10px; color: #333; font-weight: bold;"
            )
            citation_layout.addWidget(source_label)

            preview_label = QLabel(
                preview_text[:300] + "..." if len(preview_text) > 300 else preview_text
            )
            preview_label.setWordWrap(True)
            preview_label.setStyleSheet("font-size: 10px; color: #555;")
            preview_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            citation_layout.addWidget(preview_label)

            layout.addWidget(citation_frame)

        self.setStyleSheet(
            "border: 1px solid #ccc; border-radius: 5px; margin-top: 5px;"
        )


class MessageWidget(QFrame):
    """消息显示组件"""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[str] = None,
        citations: Optional[list] = None,
    ):
        """
        初始化消息组件

        Args:
            role: 消息角色 (user/assistant)
            content: 消息内容
            timestamp: 时间戳
            citations: 引用列表
        """
        super().__init__()

        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.datetime.now().strftime("%H:%M:%S")
        self.citations = citations or []
        self.citation_widget = None
        self._citations_visible = True

        self._create_ui()
        self._apply_style()

    def _create_ui(self) -> None:
        """创建界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(3)

        # 消息内容
        self.content_label = QLabel(self.content)
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        # 根据角色设置对齐
        if self.role == "user":
            self.content_label.setAlignment(Qt.AlignRight)
            layout.addWidget(self.content_label)
        else:
            self.content_label.setAlignment(Qt.AlignLeft)
            layout.addWidget(self.content_label)

        # 引用来源
        if self.citations and self.role == "assistant":
            self.citation_widget = CitationWidget(self.citations)
            layout.addWidget(self.citation_widget)

        # 时间戳
        time_label = QLabel(self.timestamp)
        time_label.setStyleSheet("font-size: 10px; color: #888;")

        if self.role == "user":
            time_label.setAlignment(Qt.AlignRight)
        else:
            time_label.setAlignment(Qt.AlignLeft)

        layout.addWidget(time_label)

    def set_citations_visible(self, visible: bool) -> None:
        """设置引用显示/隐藏"""
        self._citations_visible = visible
        if self.citation_widget:
            self.citation_widget.setVisible(visible)

    def set_citations(self, citations: list) -> None:
        """设置引用来源"""
        self.citations = citations
        if citations and not self.citation_widget:
            self.citation_widget = CitationWidget(citations)
            self.citation_widget.setVisible(self._citations_visible)
            self.layout().insertWidget(1, self.citation_widget)

    def _apply_style(self) -> None:
        """应用样式"""
        if self.role == "user":
            # 用户消息样式
            self.setStyleSheet("""
                QFrame {
                    background-color: #007acc;
                    border-radius: 10px;
                    padding: 5px;
                    margin: 2px;
                }
                QLabel {
                    color: white;
                    background: transparent;
                }
            """)
        else:
            # AI消息样式
            self.setStyleSheet("""
                QFrame {
                    background-color: #f0f0f0;
                    border-radius: 10px;
                    padding: 5px;
                    margin: 2px;
                }
                QLabel {
                    color: black;
                    background: transparent;
                }
            """)


class ChatPanel(QWidget):
    """AI对话面板"""

    # 信号定义
    message_sent = Signal(str)  # 消息发送信号
    conversation_cleared = Signal()  # 对话清空信号

    def __init__(self, config_manager: ConfigManager, ai_chat_service: AIChatService):
        """
        初始化对话面板

        Args:
            config_manager: 配置管理器
            ai_chat_service: AI对话服务
        """
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.ai_chat_service = ai_chat_service

        # 当前状态
        self.is_processing = False
        self.show_citations = False

        # 当前回复的消息组件
        self.current_response_widget = None
        self.current_response_label = None

        # 创建UI
        self._create_ui()

        # 连接信号
        self._connect_signals()

        self.logger.info("对话面板初始化完成")

    def _create_ui(self) -> None:
        """创建用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 标题
        title_label = QLabel("AI 对话")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 5px;")
        layout.addWidget(title_label)

        # 对话区域
        self._create_chat_area(layout)

        # 输入区域
        self._create_input_area(layout)

        # 状态栏
        self._create_status_bar(layout)

    def _create_chat_area(self, parent_layout: QVBoxLayout) -> None:
        """创建对话显示区域"""
        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 对话内容容器
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(5)
        self.chat_layout.setContentsMargins(5, 5, 5, 5)

        self.scroll_area.setWidget(self.chat_container)
        parent_layout.addWidget(self.scroll_area)

    def _create_input_area(self, parent_layout: QVBoxLayout) -> None:
        """创建输入区域"""
        input_layout = QHBoxLayout()
        input_layout.setSpacing(5)

        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(80)
        self.input_text.setPlaceholderText("输入您的问题...（Ctrl+Enter发送）")
        self.input_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        input_layout.addWidget(self.input_text)

        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(60, 60)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        parent_layout.addLayout(input_layout)

    def _create_status_bar(self, parent_layout: QVBoxLayout) -> None:
        """创建状态栏"""
        status_layout = QHBoxLayout()

        # 状态标签
        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)

        # 引用显示切换按钮
        self.toggle_citations_btn = QPushButton("显示引用")
        self.toggle_citations_btn.setCheckable(True)
        self.toggle_citations_btn.setChecked(False)
        self.toggle_citations_btn.clicked.connect(self._toggle_citations)
        status_layout.addWidget(self.toggle_citations_btn)

        # 清空按钮
        self.clear_btn = QPushButton("清空对话")
        self.clear_btn.clicked.connect(self._clear_conversation)
        status_layout.addWidget(self.clear_btn)

        status_layout.addStretch()

        parent_layout.addLayout(status_layout)

    def _connect_signals(self) -> None:
        """连接信号槽"""
        # 输入框回车键发送
        self.input_text.keyPressEvent = self._handle_key_press

    def _toggle_citations(self) -> None:
        """切换引用显示/隐藏"""
        self.show_citations = self.toggle_citations_btn.isChecked()
        self.toggle_citations_btn.setText(
            "隐藏引用" if self.show_citations else "显示引用"
        )

        # 更新所有消息的引用显示
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            if isinstance(widget, MessageWidget):
                widget.set_citations_visible(self.show_citations)

    def _handle_key_press(self, event) -> None:
        """处理键盘事件"""
        # Ctrl+Enter 发送消息
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            self._send_message()
        else:
            # 调用父类处理其他按键
            QTextEdit.keyPressEvent(self.input_text, event)

    def _send_message(self) -> None:
        """发送消息"""
        message = self.input_text.toPlainText().strip()

        if not message:
            QMessageBox.warning(self, "输入错误", "消息内容不能为空")
            return

        if self.is_processing:
            QMessageBox.warning(self, "系统忙碌", "正在处理上一条消息，请稍候...")
            return

        # 设置处理状态
        self.is_processing = True
        self.send_btn.setEnabled(False)
        self.status_label.setText("正在思考...")

        # 清空输入框
        self.input_text.clear()

        # 显示用户消息
        self._add_message("user", message)

        # 异步处理AI回复
        QTimer.singleShot(100, lambda: self._process_ai_response(message))

    def _process_ai_response(self, user_message: str) -> None:
        """处理AI回复"""
        # 获取配置
        config = self.config_manager.get_config()
        use_stream = config.get("chat", {}).get("stream_response", True)
        use_typing = config.get("chat", {}).get("typing_effect", True)

        if use_stream and hasattr(self.ai_chat_service, "stream_chat"):
            self._process_stream_response(user_message, use_typing)
        else:
            self._process_normal_response(user_message)

    def _process_normal_response(self, user_message: str) -> None:
        """处理普通（非流式）AI回复"""
        try:
            success, response, info = self.ai_chat_service.chat(user_message)

            if success:
                citations = [c.to_dict() for c in self.ai_chat_service.get_citations()]
                self._add_message(
                    "assistant", response, citations=citations if citations else None
                )
                token_usage = info.get("usage", {}).get("total_tokens", 0)
                self.status_label.setText(f"回复完成 (使用Token: {token_usage})")
                self.message_sent.emit(user_message)
            else:
                self._add_message("assistant", f"错误: {response}")
                self.status_label.setText("回复失败")
                self.logger.error(f"AI回复失败: {response}")

        except Exception as e:
            error_msg = f"处理回复时发生错误: {str(e)}"
            self._add_message("assistant", error_msg)
            self.status_label.setText("处理错误")
            self.logger.error(f"AI回复处理异常: {e}")

        finally:
            self.is_processing = False
            self.send_btn.setEnabled(True)
            QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))

    def _process_stream_response(self, user_message: str, use_typing: bool) -> None:
        """处理流式AI回复"""
        try:
            # 创建AI回复消息组件（初始为空）
            self._add_message("assistant", "")
            self.current_response_widget = self.chat_layout.itemAt(
                self.chat_layout.count() - 1
            ).widget()
            self.current_response_label = (
                self.current_response_widget.layout().itemAt(0).widget()
            )
            self.status_label.setText("正在生成回复...")

            full_response = ""
            typing_delay = 30 if use_typing else 0

            # 流式获取回复
            self.logger.info("开始流式响应...")
            pending_citations = None
            for result in self.ai_chat_service.stream_chat(user_message):
                self.logger.debug(f"收到流式数据: type={result.get('type')}, content_len={len(result.get('content', ''))}")
                if result["type"] == "citations":
                    pending_citations = result.get("citations")
                    self.logger.info(f"收到citations: {pending_citations}")
                elif result["type"] == "chunk":
                    # 收到文本片段
                    chunk = result["content"]
                    full_response += chunk

                    # 更新UI
                    self.current_response_label.setText(full_response)

                    # 处理打字效果延迟
                    if use_typing and typing_delay > 0:
                        QThread.msleep(typing_delay)

                    # 强制刷新UI
                    QApplication.processEvents()

                elif result["type"] == "done":
                    self.logger.info(f"流式响应完成，最终内容长度: {len(full_response)}")
                    self.current_response_label.setText(full_response)
                    citations = pending_citations or [
                        c.to_dict() for c in self.ai_chat_service.get_citations()
                    ]
                    citations = [c for c in citations if c.get("score", 0) > 0]
                    self.logger.info(f"显示citations: {citations}")
                    if citations and self.current_response_widget:
                        self.current_response_widget.set_citations(citations)
                    self.message_sent.emit(user_message)
                    self.status_label.setText("回复完成")

                elif result["type"] == "error":
                    self.logger.error(f"流式响应错误: {result['content']}")
                    self.current_response_label.setText(f"错误: {result['content']}")
                    self.status_label.setText("回复失败")

        except Exception as e:
            if self.current_response_label:
                self.current_response_label.setText(f"错误: {str(e)}")
            self.status_label.setText("回复失败")
            self.logger.error(f"AI回复处理异常: {e}")

        finally:
            self.is_processing = False
            self.send_btn.setEnabled(True)
            self.current_response_widget = None
            self.current_response_label = None
            QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))

    def _add_message(
        self, role: str, content: str, citations: Optional[list] = None
    ) -> None:
        """
        添加消息到对话区域

        Args:
            role: 消息角色
            content: 消息内容
            citations: 引用列表
        """
        message_widget = MessageWidget(role, content, citations=citations)
        message_widget.set_citations_visible(self.show_citations)

        # 添加到布局
        self.chat_layout.addWidget(message_widget)

        # 滚动到底部
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        """滚动到底部"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_conversation(self) -> None:
        """清空对话"""
        if self.is_processing:
            QMessageBox.warning(self, "系统忙碌", "正在处理消息，请稍候再清空")
            return

        # 确认清空
        reply = QMessageBox.question(
            self, "确认清空", "确定要清空当前对话吗？", QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 清空界面
            self._clear_chat_interface()

            # 清空服务端历史
            self.ai_chat_service.clear_conversation()

            # 发出清空信号
            self.conversation_cleared.emit()

            self.status_label.setText("对话已清空")
            QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))

    def _clear_chat_interface(self) -> None:
        """清空聊天界面"""
        # 移除所有消息组件
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self._add_message("system", content)

    def update_ai_service(self, ai_chat_service: AIChatService) -> None:
        """更新AI服务实例"""
        self.ai_chat_service = ai_chat_service
        self.status_label.setText("AI服务已更新")
        QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))

    def get_conversation_summary(self) -> Dict[str, Any]:
        """获取对话摘要"""
        return self.ai_chat_service.get_conversation_summary()

    def set_input_focus(self) -> None:
        """设置输入框焦点"""
        self.input_text.setFocus()

    def load_conversation_history(self, history: list) -> None:
        """加载对话历史"""
        # 先清空当前对话
        self._clear_chat_interface()

        # 添加历史消息
        for message in history:
            role = message.get("role", "")
            content = message.get("content", "")

            if role and content:
                self._add_message(role, content)
