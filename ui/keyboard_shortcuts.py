"""
键盘快捷键配置和管理
"""

from typing import Dict, List, Callable, Optional
from PySide6.QtGui import QKeySequence, QShortcut


class KeyboardShortcuts:
    """键盘快捷键管理器"""

    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.shortcuts = {}

        # 定义默认快捷键
        self.default_shortcuts = {
            # 文件操作
            "open_file": ("Ctrl+O", "打开文档"),
            "save": ("Ctrl+S", "保存"),
            "close": ("Ctrl+W", "关闭"),
            # 编辑操作
            "copy": ("Ctrl+C", "复制"),
            "paste": ("Ctrl+V", "粘贴"),
            "cut": ("Ctrl+X", "剪切"),
            "select_all": ("Ctrl+A", "全选"),
            # 视图操作
            "zoom_in": ("Ctrl++", "放大"),
            "zoom_out": ("Ctrl+-", "缩小"),
            "reset_zoom": ("Ctrl+0", "重置缩放"),
            # 文档操作
            "new_document": ("Ctrl+N", "新建文档"),
            "import_document": ("Ctrl+I", "导入文档"),
            "export_document": ("Ctrl+E", "导出文档"),
            # 对话操作
            "send_message": ("Ctrl+Enter", "发送消息"),
            "clear_chat": ("Ctrl+L", "清空对话"),
            "refresh_chat": ("F5", "刷新对话"),
            # 系统操作
            "quit": ("Ctrl+Q", "退出程序"),
            "preferences": ("Ctrl+P", "偏好设置"),
            "about": ("F1", "关于"),
            # 导航操作
            "focus_chat": ("F6", "聚焦聊天框"),
            "focus_document": ("F7", "聚焦文档栏"),
            "focus_config": ("F8", "聚焦配置栏"),
            # 搜索操作
            "search": ("Ctrl+F", "搜索"),
            "next_match": ("F3", "下一个匹配项"),
            "previous_match": ("Shift+F3", "上一个匹配项"),
        }

    def register_shortcut(
        self, name: str, key_sequence: str, description: str, callback: Callable
    ) -> bool:
        """注册快捷键"""
        try:
            shortcut = QShortcut(QKeySequence(key_sequence), self.parent)
            shortcut.activated.connect(callback)

            self.shortcuts[name] = {
                "shortcut": shortcut,
                "key_sequence": key_sequence,
                "description": description,
                "callback": callback,
                "enabled": True,
            }

            return True

        except Exception as e:
            print(f"快捷键注册失败 {name}: {e}")
            return False

    def register_default_shortcuts(self, callback_handler) -> int:
        """注册所有默认快捷键"""
        registered_count = 0

        for name, (key_seq, description) in self.default_shortcuts.items():
            # 从callback_handler中获取对应的回调函数
            callback_name = f"on_{name}"
            callback = getattr(callback_handler, callback_name, None)

            if callback and callable(callback):
                if self.register_shortcut(name, key_seq, description, callback):
                    registered_count += 1

        return registered_count

    def unregister_shortcut(self, name: str) -> bool:
        """注销快捷键"""
        if name in self.shortcuts:
            self.shortcuts[name]["shortcut"].setEnabled(False)
            del self.shortcuts[name]
            return True
        return False

    def enable_shortcut(self, name: str, enabled: bool = True) -> bool:
        """启用/禁用快捷键"""
        if name in self.shortcuts:
            self.shortcuts[name]["shortcut"].setEnabled(enabled)
            self.shortcuts[name]["enabled"] = enabled
            return True
        return False

    def get_shortcut_list(self) -> List[Dict]:
        """获取快捷键列表"""
        return [
            {
                "name": name,
                "key_sequence": info["key_sequence"],
                "description": info["description"],
                "enabled": info["enabled"],
            }
            for name, info in self.shortcuts.items()
        ]

    def get_shortcut_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取快捷键信息"""
        return self.shortcuts.get(name)

    def get_shortcut_by_sequence(self, key_sequence: str) -> Optional[Dict]:
        """根据按键序列获取快捷键信息"""
        for info in self.shortcuts.values():
            if info["key_sequence"] == key_sequence:
                return info
        return None

    def clear_all_shortcuts(self):
        """清除所有快捷键"""
        for name in list(self.shortcuts.keys()):
            self.unregister_shortcut(name)

    def export_shortcut_config(self) -> Dict:
        """导出快捷键配置"""
        return {
            "version": "1.0",
            "shortcuts": {
                name: {
                    "key_sequence": info["key_sequence"],
                    "description": info["description"],
                    "enabled": info["enabled"],
                }
                for name, info in self.shortcuts.items()
            },
        }

    def import_shortcut_config(self, config: Dict) -> int:
        """导入快捷键配置"""
        imported_count = 0

        if "shortcuts" in config:
            for name, shortcut_info in config["shortcuts"].items():
                if name in self.shortcuts:
                    # 如果快捷键已存在，更新配置
                    self.shortcuts[name]["key_sequence"] = shortcut_info.get(
                        "key_sequence", self.shortcuts[name]["key_sequence"]
                    )
                    self.enable_shortcut(name, shortcut_info.get("enabled", True))
                    imported_count += 1

        return imported_count


class MainWindowShortcutHandler:
    """主窗口快捷键处理器"""

    def __init__(self, main_window):
        self.main_window = main_window
        self.shortcut_manager = KeyboardShortcuts(main_window)

    def setup_shortcuts(self):
        """设置所有快捷键"""
        # 注册默认快捷键
        self.shortcut_manager.register_default_shortcuts(self)

        # 添加额外的自定义快捷键
        self._register_custom_shortcuts()

    def _register_custom_shortcuts(self):
        """注册自定义快捷键"""
        # 自定义快捷键可以根据需要添加
        pass

    # 以下是快捷键回调函数

    def on_open_file(self):
        """打开文件快捷键处理"""
        if hasattr(self.main_window, "open_document_dialog"):
            self.main_window.open_document_dialog()

    def on_save(self):
        """保存快捷键处理"""
        print("保存操作")

    def on_close(self):
        """关闭快捷键处理"""
        self.main_window.close()

    def on_copy(self):
        """复制快捷键处理"""
        if hasattr(self.main_window, "copy_selected_text"):
            self.main_window.copy_selected_text()

    def on_paste(self):
        """粘贴快捷键处理"""
        if hasattr(self.main_window, "paste_text"):
            self.main_window.paste_text()

    def on_cut(self):
        """剪切快捷键处理"""
        if hasattr(self.main_window, "cut_selected_text"):
            self.main_window.cut_selected_text()

    def on_select_all(self):
        """全选快捷键处理"""
        if hasattr(self.main_window, "select_all_text"):
            self.main_window.select_all_text()

    def on_send_message(self):
        """发送消息快捷键处理"""
        if hasattr(self.main_window, "send_chat_message"):
            self.main_window.send_chat_message()

    def on_clear_chat(self):
        """清空对话快捷键处理"""
        if hasattr(self.main_window, "clear_chat_history"):
            self.main_window.clear_chat_history()

    def on_refresh_chat(self):
        """刷新对话快捷键处理"""
        if hasattr(self.main_window, "refresh_chat"):
            self.main_window.refresh_chat()

    def on_focus_chat(self):
        """聚焦聊天框快捷键处理"""
        if hasattr(self.main_window, "focus_chat_input"):
            self.main_window.focus_chat_input()

    def on_focus_document(self):
        """聚焦文档栏快捷键处理"""
        if hasattr(self.main_window, "focus_document_panel"):
            self.main_window.focus_document_panel()

    def on_focus_config(self):
        """聚焦配置栏快捷键处理"""
        if hasattr(self.main_window, "focus_config_panel"):
            self.main_window.focus_config_panel()

    def on_search(self):
        """搜索快捷键处理"""
        if hasattr(self.main_window, "show_search_dialog"):
            self.main_window.show_search_dialog()

    def on_quit(self):
        """退出程序快捷键处理"""
        self.main_window.close()

    def on_preferences(self):
        """偏好设置快捷键处理"""
        if hasattr(self.main_window, "show_preferences"):
            self.main_window.show_preferences()

    def get_shortcut_help(self) -> str:
        """获取快捷键帮助信息"""
        help_text = "可用快捷键：\n"
        help_text += "=" * 40 + "\n"

        categories = {
            "文件操作": [
                "open_file",
                "save",
                "close",
                "new_document",
                "import_document",
                "export_document",
            ],
            "编辑操作": ["copy", "paste", "cut", "select_all"],
            "对话操作": ["send_message", "clear_chat", "refresh_chat"],
            "导航操作": ["focus_chat", "focus_document", "focus_config"],
            "搜索操作": ["search", "next_match", "previous_match"],
            "系统操作": ["quit", "preferences", "about"],
        }

        for category, shortcut_names in categories.items():
            help_text += f"\n{category}:\n"
            for name in shortcut_names:
                shortcut = self.shortcut_manager.get_shortcut_by_name(name)
                if shortcut and shortcut["enabled"]:
                    help_text += f"  {shortcut['key_sequence']:<15} - {shortcut['description']}\n"

        return help_text
