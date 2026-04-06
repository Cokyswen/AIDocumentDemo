"""
UI增强功能模块 - 提供加载动画、进度指示、键盘快捷键等用户体验优化功能
"""

import os
from typing import Dict, Any, Callable, List

from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
                               QFrame, QGraphicsOpacityEffect)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import Qt


class LoadingOverlay(QWidget):
    """加载覆盖层 - 在操作期间显示覆盖界面"""
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.parent_widget = parent
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI"""
        # 设置半透明黑色背景
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 150);
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # 加载文本
        self.loading_label = QLabel("处理中，请稍候...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 设置为无限模式
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                background-color: #333;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #2196F3);
                border-radius: 3px;
            }
        """)
        
        layout.addWidget(self.loading_label)
        layout.addWidget(self.progress_bar)
        
        # 隐藏初始状态
        self.hide()
        
    def show_message(self, message: str):
        """显示加载消息"""
        self.loading_label.setText(message)
        self.show()
        
    def update_progress(self, value: int, message: str = ""):
        """更新进度"""
        if value is not None:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)
        if message:
            self.loading_label.setText(message)
            
    def hide_overlay(self):
        """隐藏覆盖层"""
        self.hide()


class FadeAnimation:
    """淡入淡出动画效果"""
    
    def __init__(self, widget: QWidget):
        self.widget = widget
        self.effect = QGraphicsOpacityEffect()
        self.widget.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b"opacity")
        self.animation.setDuration(300)  # 300毫秒动画
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        
    def fade_in(self):
        """淡入效果"""
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()
        
    def fade_out(self):
        """淡出效果"""
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.start()


class KeyboardShortcutManager:
    """键盘快捷键管理器"""
    
    def __init__(self, parent_widget: QWidget):
        self.parent = parent_widget
        self.shortcuts = {}
        
    def register_shortcut(self, key_sequence: str, description: str, callback: Callable):
        """注册快捷键"""
        shortcut = QShortcut(QKeySequence(key_sequence), self.parent)
        shortcut.activated.connect(callback)
        self.shortcuts[key_sequence] = {
            'shortcut': shortcut,
            'description': description,
            'callback': callback
        }
        
    def unregister_shortcut(self, key_sequence: str):
        """注销快捷键"""
        if key_sequence in self.shortcuts:
            self.shortcuts[key_sequence]['shortcut'].setEnabled(False)
            del self.shortcuts[key_sequence]
            
    def get_shortcut_list(self) -> List[Dict[str, str]]:
        """获取快捷键列表"""
        return [
            {'key': key, 'description': info['description']}
            for key, info in self.shortcuts.items()
        ]


class DragDropHandler:
    """拖拽上传处理器"""
    
    def __init__(self, target_widget: QWidget, accepted_formats: List[str] = None):
        self.target_widget = target_widget
        self.accepted_formats = accepted_formats or ['.pdf', '.docx', '.doc', '.txt', '.md']
        self.callback = None
        
        # 启用拖拽
        self.target_widget.setAcceptDrops(True)
        
    def set_drop_callback(self, callback: Callable):
        """设置拖拽回调函数"""
        self.callback = callback
        
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # 检查文件格式
            if any(self._is_accepted_format(url.toString()) for url in urls):
                event.acceptProposedAction()
                self._show_drag_indicator(True)
                return
        event.ignore()
        
    def dragLeaveEvent(self, event):
        """拖拽离开事件"""
        self._show_drag_indicator(False)
        event.accept()
        
    def dropEvent(self, event):
        """拖放事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            file_paths = []
            
            for url in urls:
                file_path = url.toLocalFile()
                if self._is_accepted_format(file_path):
                    file_paths.append(file_path)
                    
            if file_paths and self.callback:
                self.callback(file_paths)
                
            self._show_drag_indicator(False)
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def _is_accepted_format(self, file_path: str) -> bool:
        """检查文件格式是否被接受"""
        _, ext = os.path.splitext(file_path.lower())
        return ext in self.accepted_formats
        
    def _show_drag_indicator(self, show: bool):
        """显示拖拽指示器"""
        if show:
            self.target_widget.setStyleSheet("""
                QWidget {
                    border: 2px dashed #2196F3;
                    background-color: rgba(33, 150, 243, 0.1);
                }
            """)
        else:
            self.target_widget.setStyleSheet("")


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.optimizations_applied = False
        
    def apply_ui_optimizations(self, widget: QWidget):
        """应用UI性能优化"""
        # 1. 禁用不必要的样式重绘
        widget.setUpdatesEnabled(False)
        
        # 2. 设置适当的刷新策略
        widget.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # 3. 启用双缓冲（减少闪烁）
        widget.setAttribute(Qt.WA_OpaquePaintEvent)
        
        # 4. 设置合适的更新策略
        widget.setAttribute(Qt.WA_NoSystemBackground)
        
        self.optimizations_applied = True
        
    def optimize_render_cycle(self, widget: QWidget, operation: Callable):
        """优化渲染周期"""
        # 在操作前禁用更新
        widget.setUpdatesEnabled(False)
        
        try:
            # 执行操作
            result = operation()
            
            # 启用更新并刷新
            widget.setUpdatesEnabled(True)
            widget.update()
            
            return result
            
        except Exception as e:
            # 确保异常时也启用更新
            widget.setUpdatesEnabled(True)
            raise e


class NotificationManager:
    """通知管理器"""
    
    def __init__(self, parent: QWidget):
        self.parent = parent
        self.notifications = []
        
    def show_notification(self, message: str, duration: int = 3000, 
                         notification_type: str = "info"):
        """显示通知"""
        # 创建通知小部件
        notification = QFrame(self.parent)
        notification.setFrameStyle(QFrame.Box)
        notification.setStyleSheet(self._get_style_for_type(notification_type))
        
        layout = QHBoxLayout(notification)
        label = QLabel(message)
        label.setStyleSheet("color: white; font-size: 12px;")
        layout.addWidget(label)
        
        # 显示通知
        notification.show()
        
        # 设置定时器自动关闭
        QTimer.singleShot(duration, notification.hide)
        
        return notification
        
    def _get_style_for_type(self, notification_type: str) -> str:
        """根据通知类型获取样式"""
        styles = {
            "info": "background-color: #2196F3; border: 1px solid #1976D2; border-radius: 4px;",
            "success": "background-color: #4CAF50; border: 1px solid #388E3C; border-radius: 4px;",
            "warning": "background-color: #FF9800; border: 1px solid #F57C00; border-radius: 4px;",
            "error": "background-color: #F44336; border: 1px solid #D32F2F; border-radius: 4px;"
        }
        return styles.get(notification_type, styles["info"])


def create_enhanced_widget(widget: QWidget) -> Dict[str, Any]:
    """为现有小部件添加增强功能"""
    enhancements = {}
    
    # 添加淡入淡出动画
    enhancements['animation'] = FadeAnimation(widget)
    
    # 添加快捷键支持
    enhancements['shortcuts'] = KeyboardShortcutManager(widget)
    
    # 添加拖拽支持
    enhancements['drag_drop'] = DragDropHandler(widget)
    
    # 重写拖拽事件处理方法
    widget.dragEnterEvent = enhancements['drag_drop'].dragEnterEvent
    widget.dragLeaveEvent = enhancements['drag_drop'].dragLeaveEvent
    widget.dropEvent = enhancements['drag_drop'].dropEvent
    
    return enhancements