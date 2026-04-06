"""
配置面板 - 右侧模型和对话配置区域
"""

import logging
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QTabWidget,
    QPushButton,
    QTextEdit,
    QFormLayout,
    QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt, Signal

from core.config_manager import ConfigManager


class ConfigPanel(QWidget):
    """配置面板"""

    # 信号定义
    config_changed = Signal(dict)  # 配置变更信号
    api_key_changed = Signal(str)  # API密钥变更信号

    def __init__(self, config_manager: ConfigManager):
        """
        初始化配置面板

        Args:
            config_manager: 配置管理器
        """
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager

        # 创建UI
        self._create_ui()

        # 加载配置
        self._load_config_values()

        self.logger.info("配置面板初始化完成")

    def _create_ui(self) -> None:
        """创建用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 标题
        title_label = QLabel("配置管理")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; margin: 5px;")
        layout.addWidget(title_label)

        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # AI模型配置标签页
        self._create_ai_config_tab()

        # 对话配置标签页
        self._create_chat_config_tab()

        # 文档处理配置标签页
        self._create_document_config_tab()

        # 系统配置标签页
        self._create_system_config_tab()

        # 操作按钮
        self._create_action_buttons(layout)

    def _create_ai_config_tab(self) -> None:
        """创建AI模型配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # API配置组
        api_group = QGroupBox("API 配置")
        api_layout = QFormLayout(api_group)

        # API密钥
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.textChanged.connect(self._on_api_key_changed)
        api_layout.addRow("OpenAI API Key:", self.api_key_input)

        # 显示/隐藏API密钥按钮
        key_toggle_layout = QHBoxLayout()
        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.clicked.connect(self._toggle_api_key_visibility)
        key_toggle_layout.addWidget(self.show_key_btn)
        key_toggle_layout.addStretch()
        api_layout.addRow("", key_toggle_layout)

        # API基础URL
        self.api_base_url = QLineEdit()
        self.api_base_url.textChanged.connect(self._on_config_changed)
        api_layout.addRow("API基础URL:", self.api_base_url)

        layout.addWidget(api_group)

        # 模型配置组
        model_group = QGroupBox("模型配置")
        model_layout = QFormLayout(model_group)

        # 模型选择
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(
            [
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k",
                "gpt-4",
                "gpt-4-turbo-preview",
                "gpt-4-32k",
                "GLM-4-Flash",
                "GLM-4",
                "GLM-4v",
                "自定义模型...",
            ]
        )
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_layout.addRow("模型选择:", self.model_combo)

        # 最大Token数
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 128000)
        self.max_tokens_spin.setSingleStep(1000)
        self.max_tokens_spin.setValue(16000)
        self.max_tokens_spin.valueChanged.connect(self._on_config_changed)
        model_layout.addRow("最大Token数:", self.max_tokens_spin)

        # 温度参数
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.valueChanged.connect(self._on_config_changed)
        model_layout.addRow("温度参数:", self.temperature_spin)

        layout.addWidget(model_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "AI模型配置")

    def _create_chat_config_tab(self) -> None:
        """创建对话配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # 对话行为配置组
        behavior_group = QGroupBox("对话行为")
        behavior_layout = QFormLayout(behavior_group)

        # 上下文长度
        self.context_length_spin = QSpinBox()
        self.context_length_spin.setRange(1, 20)
        self.context_length_spin.setSingleStep(1)
        self.context_length_spin.setToolTip("保存的对话轮数")
        self.context_length_spin.valueChanged.connect(self._on_config_changed)
        behavior_layout.addRow("上下文轮数:", self.context_length_spin)

        # 启用流式响应
        self.stream_response_check = QCheckBox("启用流式响应")
        self.stream_response_check.setToolTip("实时显示AI回复")
        self.stream_response_check.stateChanged.connect(self._on_config_changed)
        behavior_layout.addRow("", self.stream_response_check)

        # 启用打字效果
        self.typing_effect_check = QCheckBox("启用打字效果")
        self.typing_effect_check.setToolTip("模拟打字机效果显示回复")
        self.typing_effect_check.stateChanged.connect(self._on_config_changed)
        behavior_layout.addRow("", self.typing_effect_check)

        layout.addWidget(behavior_group)

        # 提示词配置组
        prompt_group = QGroupBox("系统提示词")
        prompt_layout = QVBoxLayout(prompt_group)

        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setMaximumHeight(150)
        self.system_prompt_edit.setPlaceholderText(
            "输入系统提示词，用于指导AI的行为（可选）..."
        )
        self.system_prompt_edit.textChanged.connect(self._on_config_changed)
        prompt_layout.addWidget(self.system_prompt_edit)

        layout.addWidget(prompt_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "对话配置")

    def _create_document_config_tab(self) -> None:
        """创建文档处理配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # 分块配置组
        chunk_group = QGroupBox("文档分块配置")
        chunk_layout = QFormLayout(chunk_group)

        # 分块大小
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(100, 2000)
        self.chunk_size_spin.setSingleStep(50)
        self.chunk_size_spin.setToolTip("每个文本块的最大字符数")
        self.chunk_size_spin.valueChanged.connect(self._on_config_changed)
        chunk_layout.addRow("分块大小:", self.chunk_size_spin)

        # 重叠大小
        self.chunk_overlap_spin = QSpinBox()
        self.chunk_overlap_spin.setRange(0, 500)
        self.chunk_overlap_spin.setSingleStep(10)
        self.chunk_overlap_spin.setToolTip("相邻文本块之间的重叠字符数")
        self.chunk_overlap_spin.valueChanged.connect(self._on_config_changed)
        chunk_layout.addRow("重叠大小:", self.chunk_overlap_spin)

        layout.addWidget(chunk_group)

        # 向量配置组
        vector_group = QGroupBox("向量数据库配置")
        vector_layout = QFormLayout(vector_group)

        # 相似度阈值
        self.similarity_threshold_spin = QDoubleSpinBox()
        self.similarity_threshold_spin.setRange(0.0, 1.0)
        self.similarity_threshold_spin.setSingleStep(0.05)
        self.similarity_threshold_spin.setToolTip("文档相似度阈值")
        self.similarity_threshold_spin.valueChanged.connect(self._on_config_changed)
        vector_layout.addRow("相似度阈值:", self.similarity_threshold_spin)

        # 最大检索结果
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(1, 10)
        self.max_results_spin.setSingleStep(1)
        self.max_results_spin.setToolTip("每次检索返回的最大文档数")
        self.max_results_spin.valueChanged.connect(self._on_config_changed)
        vector_layout.addRow("最大检索结果:", self.max_results_spin)

        # 上下文Token限制
        self.max_context_tokens_spin = QSpinBox()
        self.max_context_tokens_spin.setRange(1000, 100000)
        self.max_context_tokens_spin.setSingleStep(1000)
        self.max_context_tokens_spin.setToolTip("AI上下文中文档内容的最大Token数")
        self.max_context_tokens_spin.valueChanged.connect(self._on_config_changed)
        vector_layout.addRow("上下文Token限制:", self.max_context_tokens_spin)

        layout.addWidget(vector_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "文档处理")

    def _create_system_config_tab(self) -> None:
        """创建系统配置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # 界面配置组
        ui_group = QGroupBox("界面设置")
        ui_layout = QFormLayout(ui_group)

        # 字体大小
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 20)
        self.font_size_spin.setSingleStep(1)
        self.font_size_spin.valueChanged.connect(self._on_config_changed)
        ui_layout.addRow("字体大小:", self.font_size_spin)

        # 启用自动保存
        self.auto_save_check = QCheckBox("自动保存配置")
        self.auto_save_check.setToolTip("配置变更时自动保存")
        self.auto_save_check.stateChanged.connect(self._on_config_changed)
        ui_layout.addRow("", self.auto_save_check)

        layout.addWidget(ui_group)

        # 日志配置组
        log_group = QGroupBox("日志设置")
        log_layout = QFormLayout(log_group)

        # 日志级别
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.currentTextChanged.connect(self._on_config_changed)
        log_layout.addRow("日志级别:", self.log_level_combo)

        # 日志文件大小限制
        self.log_size_spin = QSpinBox()
        self.log_size_spin.setRange(1, 100)
        self.log_size_spin.setSuffix(" MB")
        self.log_size_spin.valueChanged.connect(self._on_config_changed)
        log_layout.addRow("日志文件大小:", self.log_size_spin)

        layout.addWidget(log_group)

        layout.addStretch()
        self.tab_widget.addTab(tab, "系统设置")

    def _create_action_buttons(self, parent_layout: QVBoxLayout) -> None:
        """创建操作按钮"""
        button_layout = QHBoxLayout()

        # 保存配置按钮
        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self._save_config)
        button_layout.addWidget(self.save_btn)

        # 重置为默认按钮
        self.reset_btn = QPushButton("重置默认")
        self.reset_btn.clicked.connect(self._reset_to_default)
        button_layout.addWidget(self.reset_btn)

        # 导入配置按钮
        self.import_btn = QPushButton("导入配置")
        self.import_btn.clicked.connect(self._import_config)
        button_layout.addWidget(self.import_btn)

        # 导出配置按钮
        self.export_btn = QPushButton("导出配置")
        self.export_btn.clicked.connect(self._export_config)
        button_layout.addWidget(self.export_btn)

        parent_layout.addLayout(button_layout)

    def _toggle_api_key_visibility(self) -> None:
        """切换API密钥显示/隐藏状态"""
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.show_key_btn.setText("隐藏")
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.show_key_btn.setText("显示")

    def _on_api_key_changed(self, text: str) -> None:
        """API密钥变更处理"""
        # 发出API密钥变更信号
        self.api_key_changed.emit(text)

    def _on_model_changed(self, text: str) -> None:
        """模型变更处理"""
        if text == "自定义模型...":
            self.model_combo.setCurrentText("")
        else:
            self._on_config_changed()

    def _on_config_changed(self, *args) -> None:
        """配置变更处理"""
        # 如果启用了自动保存，立即保存
        if hasattr(self, "auto_save_check") and self.auto_save_check.isChecked():
            self._save_config()

    def _load_config_values(self) -> None:
        """加载配置值到界面"""
        try:
            config = self.config_manager.get_config()

            # AI模型配置 (路径: ai.openai)
            ai_openai = config.get("ai", {}).get("openai", {})
            self.api_key_input.setText(ai_openai.get("api_key", ""))
            self.api_base_url.setText(ai_openai.get("base_url", ""))
            self.model_combo.setCurrentText(ai_openai.get("model", "gpt-3.5-turbo"))

            # 对话配置 (路径: ai.chat)
            ai_chat = config.get("ai", {}).get("chat", {})
            self.max_tokens_spin.setValue(ai_chat.get("max_tokens", 1000))
            self.temperature_spin.setValue(ai_chat.get("temperature", 0.7))
            self.context_length_spin.setValue(
                config.get("ai", {}).get("context", {}).get("max_history", 10)
            )

            # 文档配置
            doc_config = config.get("document", {})
            self.chunk_size_spin.setValue(
                doc_config.get("processing", {}).get("chunk_size", 1000)
            )
            self.chunk_overlap_spin.setValue(
                doc_config.get("processing", {}).get("chunk_overlap", 200)
            )

            # 向量配置
            vector_config = config.get("vector_db", {}).get("search", {})
            self.max_results_spin.setValue(vector_config.get("n_results", 5))

            # 上下文Token限制
            context_config = config.get("ai", {}).get("context", {})
            self.max_context_tokens_spin.setValue(
                context_config.get("max_doc_context_length", 4000)
            )

            # 系统配置 (路径: app.ui)
            ui_config = config.get("app", {}).get("ui", {})
            self.font_size_spin.setValue(ui_config.get("font_size", 12))

            # 对话体验配置
            chat_config = config.get("chat", {})
            self.stream_response_check.setChecked(
                chat_config.get("stream_response", True)
            )
            self.typing_effect_check.setChecked(chat_config.get("typing_effect", True))

            self.logger.info("配置值加载完成")

        except Exception as e:
            self.logger.error(f"加载配置值失败: {e}")
            QMessageBox.warning(self, "配置加载错误", f"加载配置失败: {e}")

    def _save_config(self) -> None:
        """保存配置"""
        try:
            # 使用 set_config 逐个保存配置项
            self.config_manager.set_config(
                "ai.openai.api_key", self.api_key_input.text()
            )
            self.config_manager.set_config(
                "ai.openai.base_url", self.api_base_url.text()
            )
            self.config_manager.set_config(
                "ai.openai.model", self.model_combo.currentText()
            )
            self.config_manager.set_config(
                "ai.chat.max_tokens", self.max_tokens_spin.value()
            )
            self.config_manager.set_config(
                "ai.chat.temperature", self.temperature_spin.value()
            )
            self.config_manager.set_config(
                "ai.context.max_history", self.context_length_spin.value()
            )
            self.config_manager.set_config(
                "document.processing.chunk_size", self.chunk_size_spin.value()
            )
            self.config_manager.set_config(
                "document.processing.chunk_overlap", self.chunk_overlap_spin.value()
            )
            self.config_manager.set_config(
                "vector_db.search.n_results", self.max_results_spin.value()
            )
            self.config_manager.set_config(
                "ai.context.max_doc_context_length",
                self.max_context_tokens_spin.value(),
            )
            self.config_manager.set_config(
                "app.ui.font_size", self.font_size_spin.value()
            )
            # 对话体验配置
            self.config_manager.set_config(
                "chat.stream_response", self.stream_response_check.isChecked()
            )
            self.config_manager.set_config(
                "chat.typing_effect", self.typing_effect_check.isChecked()
            )

            # 保存到文件
            if self.config_manager.save_config():
                # 发出配置变更信号
                self.config_changed.emit(self.config_manager.get_config())

                self.logger.info("配置保存成功")

                # 显示成功消息
                QMessageBox.information(self, "保存成功", "配置已成功保存")
            else:
                raise Exception("配置管理器保存失败")

        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存配置时发生错误: {e}")

    def _reset_to_default(self) -> None:
        """重置为默认配置"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置所有配置为默认值吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                # 重新加载配置文件（会使用默认配置）
                self.config_manager.reload_config()
                self._load_config_values()

                # 发出重置信号
                self.config_changed.emit(self.config_manager.get_config())

                QMessageBox.information(self, "重置成功", "配置已重置为默认值")

            except Exception as e:
                QMessageBox.critical(self, "重置失败", f"重置配置时发生错误: {e}")

    def _import_config(self) -> None:
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择配置文件", "", "JSON Files (*.json);;YAML Files (*.yaml *.yml)"
        )

        if file_path:
            try:
                if self.config_manager.import_config(file_path):
                    # 重新加载配置
                    self._load_config_values()

                    # 发出配置变更信号
                    config = self.config_manager.get_config()
                    self.config_changed.emit(config)

                    QMessageBox.information(self, "导入成功", "配置已成功导入")
                else:
                    raise Exception("配置导入失败")

            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"导入配置时发生错误: {e}")

    def _export_config(self) -> None:
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存配置文件",
            "config",
            "JSON Files (*.json);;YAML Files (*.yaml *.yml)",
        )

        if file_path:
            try:
                if self.config_manager.export_config(file_path):
                    QMessageBox.information(self, "导出成功", "配置已成功导出")
                else:
                    raise Exception("配置导出失败")

            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出配置时发生错误: {e}")

    def get_current_config(self) -> Dict[str, Any]:
        """获取当前面板中的配置值"""
        config = {}

        config["openai"] = {
            "api_key": self.api_key_input.text(),
            "model": self.model_combo.currentText(),
            "max_tokens": self.max_tokens_spin.value(),
            "temperature": self.temperature_spin.value(),
        }

        config["chat"] = {
            "context_length": self.context_length_spin.value(),
            "stream_response": self.stream_response_check.isChecked(),
            "typing_effect": self.typing_effect_check.isChecked(),
            "system_prompt": self.system_prompt_edit.toPlainText(),
        }

        config["document"] = {
            "chunk_size": self.chunk_size_spin.value(),
            "chunk_overlap": self.chunk_overlap_spin.value(),
            "similarity_threshold": self.similarity_threshold_spin.value(),
            "max_results": self.max_results_spin.value(),
        }

        config["system"] = {
            "font_size": self.font_size_spin.value(),
            "auto_save": self.auto_save_check.isChecked(),
            "log_level": self.log_level_combo.currentText(),
            "log_size": self.log_size_spin.value(),
        }

        return config

    def update_from_config(self, config: Dict[str, Any]) -> None:
        """从现有配置更新界面"""
        try:
            # 临时断开信号连接，避免触发保存
            self._disconnect_signals()

            # AI模型配置
            ai_openai = config.get("ai", {}).get("openai", {})
            self.api_key_input.setText(ai_openai.get("api_key", ""))
            self.api_base_url.setText(ai_openai.get("base_url", ""))
            self.model_combo.setCurrentText(ai_openai.get("model", "gpt-3.5-turbo"))

            # 对话配置
            ai_chat = config.get("ai", {}).get("chat", {})
            self.max_tokens_spin.setValue(ai_chat.get("max_tokens", 1000))
            self.temperature_spin.setValue(ai_chat.get("temperature", 0.7))

            # 文档配置
            doc_config = config.get("document", {})
            self.chunk_size_spin.setValue(
                doc_config.get("processing", {}).get("chunk_size", 1000)
            )
            self.chunk_overlap_spin.setValue(
                doc_config.get("processing", {}).get("chunk_overlap", 200)
            )

            # 向量配置
            self.max_results_spin.setValue(
                config.get("vector_db", {}).get("search", {}).get("n_results", 5)
            )

            # 重新连接信号
            # 注：当前实现中信号始终连接

        except Exception as e:
            self.logger.error(f"从配置更新界面失败: {e}")
