"""
主窗口类 - 应用程序的主界面框架
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QHBoxLayout,
    QWidget,
    QSplitter,
    QStatusBar,
    QMessageBox,
    QFileDialog,
    QToolBar,
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QIcon, QKeySequence

from ui.document_panel import DocumentPanel
from ui.chat_panel import ChatPanel
from ui.config_panel import ConfigPanel
from core.config_manager import ConfigManager
from core.document_manager import create_document_manager
from core.indexing.vector_database import create_vector_database
from core.ai_chat import create_ai_chat_service
from core.app_state_manager import AppStateManager


class MainWindow(QMainWindow):
    """应用程序主窗口"""

    def __init__(self, config_manager: ConfigManager):
        """
        初始化主窗口

        Args:
            config_manager: 配置管理器实例
        """
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager

        # 加载配置
        self.config = self.config_manager.get_config()

        # 初始化核心组件
        self._init_core_components()

        # 设置窗口属性
        self._setup_window()

        # 创建UI组件
        self._create_ui()

        # 连接信号槽
        self._connect_signals()

        # 加载窗口状态
        self._load_window_state()

        self.logger.info("主窗口初始化完成")

    def _init_core_components(self) -> None:
        """初始化核心组件"""
        try:
            # 初始化向量数据库
            self.vector_db = create_vector_database(self.config)

            # 初始化文档管理器
            self.document_manager = create_document_manager(self.config)

            # 初始化AI对话服务
            self.ai_chat_service = create_ai_chat_service(self.config, self.vector_db)

            # 初始化应用状态管理器
            self.app_state_manager = AppStateManager(
                self.config_manager, self.document_manager, self.vector_db
            )

            self.logger.info("核心组件初始化成功")

        except Exception as e:
            self.logger.error(f"核心组件初始化失败: {e}")
            QMessageBox.critical(
                self,
                "初始化错误",
                f"应用程序初始化失败:\n{str(e)}\n\n请检查配置和依赖项。",
            )
            # 设置标记以便稍后重试
            self.core_components_initialized = False
            return

        self.core_components_initialized = True

    def _setup_window(self) -> None:
        """设置窗口属性"""
        # 设置窗口标题
        app_name = self.config.get("app", {}).get("name", "文档问答桌面应用")
        self.setWindowTitle(app_name)

        # 设置窗口大小
        ui_config = self.config.get("app", {}).get("ui", {})
        window_config = ui_config.get("window", {})

        default_width = window_config.get("width", 1200)
        default_height = window_config.get("height", 800)

        self.resize(default_width, default_height)

        # 设置窗口图标（如果有）
        self._set_window_icon()

    def _set_window_icon(self) -> None:
        """设置窗口图标"""
        icon_paths = ["assets/icon.png", "assets/icon.ico", "icon.png", "icon.ico"]

        for path in icon_paths:
            if Path(path).exists():
                try:
                    self.setWindowIcon(QIcon(path))
                    self.logger.info(f"设置窗口图标: {path}")
                    break
                except Exception as e:
                    self.logger.warning(f"设置图标失败 {path}: {e}")

    def _create_ui(self) -> None:
        """创建用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 创建分割器
        self.splitter = QSplitter(Qt.Horizontal)

        # 创建左侧文档面板 (25%)
        self.document_panel = DocumentPanel(
            self.config_manager, self.document_manager, self.vector_db
        )

        # 创建中间对话面板 (50%)
        self.chat_panel = ChatPanel(self.config_manager, self.ai_chat_service)

        # 创建右侧配置面板 (25%)
        self.config_panel = ConfigPanel(self.config_manager)

        # 添加到分割器
        self.splitter.addWidget(self.document_panel)
        self.splitter.addWidget(self.chat_panel)
        self.splitter.addWidget(self.config_panel)

        # 存储面板引用以便状态管理器使用
        self.app_state_manager.document_panel = self.document_panel
        self.app_state_manager.chat_panel = self.chat_panel
        self.app_state_manager.config_panel = self.config_panel

        # 设置初始大小比例
        total_width = self.width()
        self.splitter.setSizes(
            [
                int(total_width * 0.25),  # 左侧25%
                int(total_width * 0.50),  # 中间50%
                int(total_width * 0.25),  # 右侧25%
            ]
        )

        # 添加到主布局
        main_layout.addWidget(self.splitter)

        # 创建菜单栏
        self._create_menu_bar()

        # 创建状态栏
        self._create_status_bar()

        # 创建工具栏（可选）
        self._create_toolbar()

    def _create_menu_bar(self) -> None:
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        # 打开文档操作
        open_action = QAction("打开文档", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_document)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        # 退出操作
        exit_action = QAction("退出", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")

        # 清空对话历史
        clear_chat_action = QAction("清空对话", self)
        clear_chat_action.triggered.connect(self._clear_chat_history)
        edit_menu.addAction(clear_chat_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图")

        # 显示/隐藏面板操作
        toggle_doc_action = QAction("显示/隐藏文档面板", self)
        toggle_doc_action.setShortcut("Ctrl+D")
        toggle_doc_action.triggered.connect(self._toggle_document_panel)
        view_menu.addAction(toggle_doc_action)

        toggle_config_action = QAction("显示/隐藏配置面板", self)
        toggle_config_action.setShortcut("Ctrl+C")
        toggle_config_action.triggered.connect(self._toggle_config_panel)
        view_menu.addAction(toggle_config_action)

        view_menu.addSeparator()

        # 检索测试工具
        retrieval_test_action = QAction("检索对比测试", self)
        retrieval_test_action.setShortcut("Ctrl+R")
        retrieval_test_action.triggered.connect(self._open_retrieval_test)
        view_menu.addAction(retrieval_test_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_status_bar(self) -> None:
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 初始状态显示
        self.status_bar.showMessage("应用程序就绪")

    def _create_toolbar(self) -> None:
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        # 可以在这里添加常用工具按钮
        # 例如：上传文档、清空对话等

    def _connect_signals(self) -> None:
        """连接信号槽"""
        # 文档面板信号
        if hasattr(self.document_panel, "document_selected"):
            self.document_panel.document_selected.connect(self._on_document_selected)

        if hasattr(self.document_panel, "document_processed"):
            self.document_panel.document_processed.connect(self._on_document_processed)

        if hasattr(self.document_panel, "document_uploaded"):
            self.document_panel.document_uploaded.connect(self._on_document_uploaded)

        if hasattr(self.document_panel, "document_deleted"):
            self.document_panel.document_deleted.connect(self._on_document_deleted)

        # 聊天面板信号
        if hasattr(self.chat_panel, "message_sent"):
            self.chat_panel.message_sent.connect(self._on_message_sent)

        if hasattr(self.chat_panel, "conversation_cleared"):
            self.chat_panel.conversation_cleared.connect(self._on_conversation_cleared)

        # 配置面板信号
        if hasattr(self.config_panel, "config_changed"):
            self.config_panel.config_changed.connect(self._on_config_changed)

        if hasattr(self.config_panel, "api_key_changed"):
            self.config_panel.api_key_changed.connect(self._on_api_key_changed)

        # 应用状态管理器信号
        if hasattr(self.app_state_manager, "state_changed"):
            self.app_state_manager.state_changed.connect(self._on_app_state_changed)

        if hasattr(self.app_state_manager, "config_changed"):
            self.app_state_manager.config_changed.connect(self._on_app_config_changed)

        if hasattr(self.app_state_manager, "document_processed"):
            self.app_state_manager.document_processed.connect(
                self._on_app_document_processed
            )

        if hasattr(self.app_state_manager, "chat_message_added"):
            self.app_state_manager.chat_message_added.connect(
                self._on_app_chat_message_added
            )

        if hasattr(self.app_state_manager, "error_occurred"):
            self.app_state_manager.error_occurred.connect(self._on_app_error_occurred)

        # 配置管理器信号
        self.config_manager.add_listener(self._on_global_config_changed)

    def _load_window_state(self) -> None:
        """加载窗口状态"""
        settings = QSettings("MySite", "DocumentQA")

        # 加载窗口几何信息
        geometry = settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # 加载分割器状态
        splitter_state = settings.value("splitter_state")
        if splitter_state:
            self.splitter.restoreState(splitter_state)

        # 加载窗口最大化状态
        maximized = settings.value("window_maximized", False, type=bool)
        if maximized:
            self.showMaximized()

    def closeEvent(self, event) -> None:
        """窗口关闭事件"""
        self._save_window_state()

        # 清理资源
        if hasattr(self, "vector_db") and hasattr(self.vector_db, "close"):
            self.vector_db.close()

        event.accept()

    def _save_window_state(self) -> None:
        """保存窗口状态"""
        settings = QSettings("MySite", "DocumentQA")

        # 保存窗口几何信息
        settings.setValue("window_geometry", self.saveGeometry())

        # 保存分割器状态
        settings.setValue("splitter_state", self.splitter.saveState())

        # 保存窗口最大化状态
        settings.setValue("window_maximized", self.isMaximized())

    def _open_document(self) -> None:
        """打开文档文件"""
        if not self.core_components_initialized:
            QMessageBox.warning(self, "警告", "核心组件未初始化，无法处理文档")
            return

        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        # 设置文件过滤器
        supported_extensions = self.config.get("document", {}).get(
            "supported_extensions", []
        )
        file_filters = [f"*{ext}" for ext in supported_extensions]
        file_dialog.setNameFilter(f"文档文件 ({' '.join(file_filters)})")

        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            for file_path in file_paths:
                self.document_panel.add_document(file_path)

    def _clear_chat_history(self) -> None:
        """清空对话历史"""
        if hasattr(self, "ai_chat_service"):
            self.ai_chat_service.clear_conversation()
            self.status_bar.showMessage("对话历史已清空", 3000)

    def _toggle_document_panel(self) -> None:
        """切换文档面板显示"""
        self.document_panel.setVisible(not self.document_panel.isVisible())

    def _toggle_config_panel(self) -> None:
        """切换配置面板显示"""
        self.config_panel.setVisible(not self.config_panel.isVisible())

    def _open_retrieval_test(self) -> None:
        """打开检索对比测试窗口"""
        try:
            from ui.retrieval_test_window import RetrievalTestWindow

            if (
                not hasattr(self, "_retrieval_test_window")
                or self._retrieval_test_window is None
            ):
                self._retrieval_test_window = RetrievalTestWindow()

            self._retrieval_test_window.show()
            self._retrieval_test_window.raise_()
            self._retrieval_test_window.activateWindow()
        except Exception as e:
            self.logger.error(f"打开检索测试窗口失败: {e}")
            QMessageBox.warning(self, "错误", f"打开检索测试窗口失败:\n{str(e)}")

    def _show_about(self) -> None:
        """显示关于对话框"""
        app_info = self.config.get("app", {})
        about_text = f"""
        {app_info.get("name", "文档问答桌面应用")}
        版本: {app_info.get("version", "1.0.0")}
        
        基于PySide6和ChromaDB的文档问答应用程序
        支持PDF、Word、文本等多种文档格式
        集成OpenAI AI对话服务
        
        © 2025 {app_info.get("organization", "MySite")}
        """

        QMessageBox.about(self, "关于", about_text.strip())

    def _on_document_selected(self, file_info: dict) -> None:
        """文档选择处理"""
        self.status_bar.showMessage(
            f"已选择文档: {file_info.get('file_name', '未知')}", 3000
        )

        # 通过状态管理器处理文档选择
        self.app_state_manager.set_current_document(file_info)

    def _on_document_processed(self, result: dict) -> None:
        """文档处理完成处理"""
        if result.get("success"):
            self.status_bar.showMessage("文档处理完成", 3000)
        else:
            self.status_bar.showMessage("文档处理失败", 5000)

    def _on_document_uploaded(self, result: dict) -> None:
        """文档上传处理 - 将文档块存储到向量数据库"""
        if result.get("success"):
            chunks = result.get("chunks", [])
            file_info = result.get("file_info", {})
            file_path = result.get("file_path", "")

            if chunks:
                try:
                    # 提取文本内容和元数据
                    texts = []
                    metadatas = []
                    for i, chunk in enumerate(chunks):
                        if isinstance(chunk, dict):
                            texts.append(chunk.get("content", ""))
                            meta = {
                                "source": file_info.get("file_name", ""),
                                "file_path": file_path,
                                "chunk_index": i,
                            }
                            meta.update(chunk.get("metadata", {}))
                            metadatas.append(meta)
                        else:
                            texts.append(str(chunk))
                            metadatas.append(
                                {
                                    "source": file_info.get("file_name", ""),
                                    "file_path": file_path,
                                    "chunk_index": i,
                                }
                            )

                    # 添加到向量数据库
                    doc_ids = self.vector_db.add(texts, metadatas)
                    self.logger.info(f"文档已存储到向量数据库，共 {len(doc_ids)} 个块")

                except Exception as e:
                    self.logger.error(f"文档存储到向量数据库失败: {e}")
                    QMessageBox.warning(self, "存储失败", f"文档存储失败: {str(e)}")

    def _on_document_deleted(self, document_id: str) -> None:
        """文档删除处理"""
        # 通过状态管理器处理文档删除
        self.app_state_manager.delete_document(document_id)

    def _on_message_sent(self, message: str) -> None:
        """消息发送处理"""
        # AI对话已由chat_panel直接处理，这里只需更新UI状态
        pass

    def _on_conversation_cleared(self) -> None:
        """对话清空处理"""
        # 通过状态管理器处理对话清空
        self.app_state_manager.clear_chat_history()

    def _on_api_key_changed(self, api_key: str) -> None:
        """API密钥变更处理"""
        # 更新配置
        config = self.config_manager.get_config()
        if "openai" not in config:
            config["openai"] = {}
        config["openai"]["api_key"] = api_key

        # 通过状态管理器更新配置
        self.app_state_manager.update_config(config)

    def _on_app_state_changed(self, state_update: dict) -> None:
        """应用状态变更处理"""
        # 处理状态变更，更新UI
        if state_update.get("is_processing"):
            self.status_bar.showMessage(
                f"正在处理: {state_update.get('processing_stage', '')}"
            )
        else:
            self.status_bar.showMessage("就绪", 3000)

    def _on_app_config_changed(self, new_config: dict) -> None:
        """应用配置变更处理"""
        # 通知配置面板更新
        if hasattr(self.config_panel, "update_from_config"):
            self.config_panel.update_from_config(new_config)

    def _on_app_document_processed(self, result: dict) -> None:
        """应用文档处理完成处理"""
        # 通知文档面板更新
        if hasattr(self.document_panel, "on_document_processed"):
            self.document_panel.on_document_processed(result)

        # 显示状态消息
        name = result.get("document_name", "")
        chunks = result.get("chunk_count", 0)
        self.status_bar.showMessage(f"文档 '{name}' 处理完成 ({chunks}个分块)", 5000)

    def _on_app_chat_message_added(self, message: dict) -> None:
        """应用聊天消息添加处理"""
        # 通知聊天面板更新
        if hasattr(self.chat_panel, "add_ai_response"):
            self.chat_panel.add_ai_response(message)

    def _on_app_error_occurred(self, error_message: str) -> None:
        """应用错误发生处理"""
        # 显示错误消息
        self.status_bar.showMessage(f"错误: {error_message}", 5000)
        QMessageBox.warning(self, "错误", error_message)

    def _on_config_changed(self, key: str, value: any) -> None:
        """配置变更处理"""
        # 更新全局配置
        self.config_manager.set_config(key, value)

        # 根据配置变更更新界面
        self._handle_config_update(key, value)

    def _on_global_config_changed(self, key: str, value: any) -> None:
        """全局配置变更处理"""
        # 更新界面状态
        self._handle_config_update(key, value)

    def _handle_config_update(self, key: str, value: any) -> None:
        """处理配置更新"""
        if key == "app.ui.theme":
            self._apply_theme(value)
        elif key == "ai.openai.api_key":
            self._update_ai_service()

        # 可以添加更多配置更新处理

    def _apply_theme(self, theme: str) -> None:
        """应用主题"""
        # 这里可以实现主题切换逻辑
        # 目前使用系统默认主题
        pass

    def _update_ai_service(self) -> None:
        """更新AI服务"""
        # 重新初始化AI服务
        try:
            self.ai_chat_service = create_ai_chat_service(self.config, self.vector_db)
            self.chat_panel.update_ai_service(self.ai_chat_service)
            self.status_bar.showMessage("AI服务配置已更新", 3000)
        except Exception as e:
            self.logger.error(f"更新AI服务失败: {e}")
            self.status_bar.showMessage("AI服务更新失败", 5000)
