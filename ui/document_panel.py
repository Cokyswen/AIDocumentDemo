"""
文档选择面板 - 左侧文档管理和选择区域
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QIcon

from core.config_manager import ConfigManager
from core.document_manager import DocumentManager


class DocumentProcessingThread(QThread):
    """文档处理线程"""

    finished = Signal(dict)  # 处理完成信号
    progress = Signal(int)  # 进度信号

    def __init__(self, file_path: Path, document_manager: DocumentManager):
        super().__init__()
        self.file_path = file_path
        self.document_manager = document_manager

    def run(self):
        """线程执行函数"""
        try:
            # 处理文档
            success, chunks, file_info = self.document_manager.process(self.file_path)

            result = {
                "success": success,
                "chunks": chunks,
                "file_info": file_info,
                "file_path": str(self.file_path),
            }

            self.finished.emit(result)

        except Exception as e:
            result = {
                "success": False,
                "error": str(e),
                "file_path": str(self.file_path),
            }
            self.finished.emit(result)


class DocumentPanel(QWidget):
    """文档选择面板"""

    # 信号定义
    document_selected = Signal(dict)  # 文档选择信号
    document_processed = Signal(dict)  # 文档处理完成信号
    document_uploaded = Signal(dict)  # 文档上传并处理完成信号（包含chunks）

    def __init__(
        self,
        config_manager: ConfigManager,
        document_manager: DocumentManager,
        vector_database=None,
    ):
        """
        初始化文档面板

        Args:
            config_manager: 配置管理器
            document_manager: 文档管理器
            vector_database: 向量数据库实例（用于加载已存储的文档）
        """
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.document_manager = document_manager
        self.vector_database = vector_database

        # 文档列表和状态跟踪
        self.documents: List[Dict[str, Any]] = []
        self.processing_threads: List[DocumentProcessingThread] = []

        # 创建UI
        self._create_ui()

        # 连接信号
        self._connect_signals()

        # 加载已有文档
        self._load_existing_documents()

        self.logger.info("文档面板初始化完成")

    def set_vector_database(self, vector_database):
        """设置向量数据库并加载已有文档"""
        self.vector_database = vector_database
        self._load_existing_documents()

    def _load_existing_documents(self):
        """从向量数据库加载已有的文档"""
        if not self.vector_database:
            return

        try:
            all_docs = self.vector_database.collection.get(include=["metadatas"])

            # 检查是否有文档
            metadatas = all_docs.get("metadatas")
            if not metadatas:
                self.logger.info("向量数据库为空")
                return

            # 按来源分组统计
            source_stats = {}
            for meta in metadatas:
                source = meta.get("source", "")
                if source and source not in source_stats:
                    source_stats[source] = {
                        "file_name": source,
                        "file_path": meta.get("file_path", ""),
                        "chunk_count": 0,
                        "file_size": meta.get("file_size", 0),
                    }
                if source in source_stats:
                    source_stats[source]["chunk_count"] += 1

            # 添加到文档列表
            for source, stats in source_stats.items():
                # 检查是否已在列表中
                if any(
                    doc["file_info"].get("file_name") == source
                    for doc in self.documents
                ):
                    continue

                document_item = {
                    "file_path": stats["file_path"],
                    "file_info": {
                        "file_name": stats["file_name"],
                        "file_path": stats["file_path"],
                        "file_size": stats.get("file_size", 0),
                        "chunk_count": stats["chunk_count"],
                    },
                    "status": "已存储",
                    "item": None,
                    "is_from_db": True,  # 标记为从数据库加载
                }

                self.documents.append(document_item)
                self._add_document_to_list(document_item["file_info"], "已存储")

            self.logger.info(f"从向量数据库加载了 {len(source_stats)} 个文档")

        except Exception as e:
            self.logger.error(f"从向量数据库加载文档失败: {e}")

    def _create_ui(self) -> None:
        """创建用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # 标题
        title_layout = QHBoxLayout()
        title_label = QLabel("文档管理")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.doc_count_label = QLabel("(0)")
        self.doc_count_label.setStyleSheet("color: gray; font-size: 12px;")

        title_layout.addWidget(title_label)
        title_layout.addWidget(self.doc_count_label)
        title_layout.addStretch()

        # 刷新按钮
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_btn.setToolTip("刷新文档列表")
        self.refresh_btn.clicked.connect(self._load_existing_documents)
        title_layout.addWidget(self.refresh_btn)

        layout.addLayout(title_layout)

        # 操作按钮区域
        button_layout = QHBoxLayout()

        # 上传按钮
        self.upload_btn = QPushButton("上传文档")
        self.upload_btn.setIcon(QIcon.fromTheme("document-open"))
        button_layout.addWidget(self.upload_btn)

        # 删除按钮
        self.delete_btn = QPushButton("删除")
        self.delete_btn.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)

        # 清空按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setIcon(QIcon.fromTheme("edit-clear"))
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        # 文档列表
        self.doc_list = QTreeWidget()
        self.doc_list.setHeaderLabels(["文档名称", "大小", "块数", "状态"])
        self.doc_list.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.doc_list)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # 文档信息区域
        self.info_label = QLabel("选择文档查看详细信息")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            "background-color: #f0f0f0; padding: 5px; border-radius: 3px;"
        )
        layout.addWidget(self.info_label)

    def _connect_signals(self) -> None:
        """连接信号槽"""
        # 按钮信号
        self.upload_btn.clicked.connect(self._upload_documents)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.clear_btn.clicked.connect(self._clear_all)

        # 列表选择信号
        self.doc_list.itemSelectionChanged.connect(self._on_selection_changed)

    def _update_doc_count(self) -> None:
        """更新文档计数显示"""
        total_docs = len(self.documents)
        stored_docs = sum(1 for doc in self.documents if doc.get("status") == "已存储")
        processed_docs = sum(
            1 for doc in self.documents if doc.get("status") in ["处理完成", "已存储"]
        )

        self.doc_count_label.setText(f"({total_docs}个文档)")

        if stored_docs > 0:
            self.status_label.setText(f"数据库: {stored_docs}个文档")

    def _upload_documents(self) -> None:
        """上传文档"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        # 设置文件过滤器
        supported_extensions = self.config_manager.get_config(
            "document.supported_extensions",
            [".pdf", ".docx", ".txt", ".md", ".markdown"],
        )

        file_filters = [f"*{ext}" for ext in supported_extensions]
        file_dialog.setNameFilter(f"文档文件 ({' '.join(file_filters)})")

        if file_dialog.exec():
            file_paths = file_dialog.selectedFiles()
            for file_path in file_paths:
                self.add_document(file_path)

    def add_document(self, file_path: str) -> None:
        """
        添加文档到列表并开始处理

        Args:
            file_path: 文件路径
        """
        file_path_obj = Path(file_path)

        # 验证文档
        validation = self.document_manager.validate_document(file_path_obj)

        if not validation["valid"]:
            QMessageBox.warning(self, "文档验证失败", validation["reason"])
            return

        # 检查是否已存在
        for doc in self.documents:
            if doc["file_path"] == str(file_path_obj):
                QMessageBox.information(self, "提示", "文档已在列表中")
                return

        # 添加到文档列表
        file_info = validation["file_info"]
        document_item = {
            "file_path": str(file_path_obj),
            "file_info": file_info,
            "status": "等待处理",
            "item": None,
        }

        self.documents.append(document_item)

        # 在列表中显示
        self._add_document_to_list(file_info, "等待处理")

        # 开始处理文档
        self._process_document(file_path_obj)

    def _add_document_to_list(self, file_info: Dict[str, Any], status: str) -> None:
        """添加文档到列表控件"""
        item = QTreeWidgetItem(self.doc_list)

        # 文档名称
        item.setText(0, file_info.get("file_name", "未知"))

        # 文件大小
        size_bytes = file_info.get("file_size", 0)
        size_str = self._format_file_size(size_bytes)
        item.setText(1, size_str)

        # 块数
        chunk_count = file_info.get("chunk_count", "-")
        item.setText(2, str(chunk_count) if chunk_count else "-")

        # 状态
        item.setText(3, status)

        # 存储文件路径在item中
        item.setData(0, Qt.UserRole, file_info.get("file_path", ""))

        # 更新文档项的引用
        for doc in self.documents:
            if doc["file_info"].get("file_path") == file_info.get("file_path"):
                doc["item"] = item
                break

        # 更新文档计数
        self._update_doc_count()

    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _process_document(self, file_path: Path) -> None:
        """处理文档"""
        # 创建处理线程
        thread = DocumentProcessingThread(file_path, self.document_manager)
        thread.finished.connect(self._on_document_processed)

        self.processing_threads.append(thread)

        # 更新UI状态
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"正在处理: {file_path.name}")

        # 开始处理
        thread.start()

    def _on_document_processed(self, result: Dict[str, Any]) -> None:
        """文档处理完成回调"""
        file_path = result.get("file_path", "")

        # 更新文档状态
        for doc in self.documents:
            if doc["file_path"] == file_path:
                if result["success"]:
                    doc["status"] = "处理完成"
                    doc["chunks"] = result.get("chunks", [])

                    if doc["item"]:
                        chunk_count = len(result.get("chunks", []))
                        doc["item"].setText(2, str(chunk_count))
                        doc["item"].setText(3, "处理完成")
                        doc["item"].setForeground(3, Qt.darkGreen)

                    self.logger.info(f"文档处理成功: {file_path}")
                else:
                    doc["status"] = "处理失败"

                    if doc["item"]:
                        doc["item"].setText(3, "处理失败")
                        doc["item"].setForeground(3, Qt.red)

                    self.logger.error(f"文档处理失败: {file_path}")
                break

        # 移除完成的线程
        for thread in self.processing_threads[:]:
            if not thread.isRunning():
                self.processing_threads.remove(thread)

        # 更新UI状态
        if not self.processing_threads:
            self.progress_bar.setVisible(False)
            self.status_label.setText("就绪")

        # 更新文档计数
        self._update_doc_count()

        # 发出处理完成信号
        self.document_processed.emit(result)

        # 如果处理成功，发送上传信号（包含chunks供向量数据库存储）
        if result["success"]:
            self.document_uploaded.emit(result)

    def _on_selection_changed(self) -> None:
        """文档选择变化处理"""
        selected_items = self.doc_list.selectedItems()

        if not selected_items:
            self.delete_btn.setEnabled(False)
            self.info_label.setText("选择文档查看详细信息")
            return

        self.delete_btn.setEnabled(True)

        selected_item = selected_items[0]
        file_path = selected_item.data(0, Qt.UserRole)

        # 查找文档信息
        for doc in self.documents:
            if doc["file_path"] == file_path:
                file_info = doc["file_info"]
                status = doc["status"]

                # 显示详细信息
                info_text = f"""
                <b>文档名称:</b> {file_info.get("file_name", "未知")}<br>
                <b>文件路径:</b> {file_info.get("file_path", "未知")}<br>
                <b>文件大小:</b> {self._format_file_size(file_info.get("file_size", 0))}<br>
                <b>修改时间:</b> {file_info.get("modified_time", "未知")}<br>
                <b>处理状态:</b> {status}<br>
                """

                self.info_label.setText(info_text.strip())

                # 发出选择信号
                self.document_selected.emit(file_info)
                break

    def _delete_selected(self) -> None:
        """删除选中的文档"""
        selected_items = self.doc_list.selectedItems()

        if not selected_items:
            return

        selected_item = selected_items[0]
        file_path = selected_item.data(0, Qt.UserRole)

        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除文档 '{selected_item.text(0)}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # 从列表中移除
            index = self.doc_list.indexOfTopLevelItem(selected_item)
            self.doc_list.takeTopLevelItem(index)

            # 从文档列表中移除
            self.documents = [
                doc for doc in self.documents if doc["file_path"] != file_path
            ]

            self.status_label.setText("文档已删除")
            QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))

    def _clear_all(self) -> None:
        """清空所有文档"""
        if not self.documents:
            return

        # 确认清空
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确定要清空所有 {len(self.documents)} 个文档吗？",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # 停止所有处理线程
            for thread in self.processing_threads:
                if thread.isRunning():
                    thread.terminate()

            self.processing_threads.clear()

            # 清空列表
            self.doc_list.clear()
            self.documents.clear()

            # 更新UI
            self.progress_bar.setVisible(False)
            self.delete_btn.setEnabled(False)
            self.info_label.setText("选择文档查看详细信息")
            self.status_label.setText("所有文档已清空")

            QTimer.singleShot(3000, lambda: self.status_label.setText("就绪"))

    def get_processed_documents(self) -> List[Dict[str, Any]]:
        """获取已处理的文档列表"""
        return [doc for doc in self.documents if doc["status"] == "处理完成"]

    def get_document_chunks(self, file_path: str) -> List[str]:
        """获取指定文档的文本块"""
        for doc in self.documents:
            if doc["file_path"] == file_path and doc["status"] == "处理完成":
                return doc.get("chunks", [])
        return []

    def update_document_status(self, file_path: str, status: str) -> None:
        """更新文档状态"""
        for doc in self.documents:
            if doc["file_path"] == file_path:
                doc["status"] = status
                if doc["item"]:
                    doc["item"].setText(2, status)
                break
