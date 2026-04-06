"""
配置管理器 - 处理应用程序配置的读取、保存和验证
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml


class ConfigManager:
    """配置管理器类"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径，如果为None则使用默认路径
        """
        self.logger = logging.getLogger(__name__)

        # 确定配置文件路径
        if config_file is None:
            project_root = Path(__file__).parent.parent
            self.config_file = project_root / "config" / "settings.yaml"
        else:
            self.config_file = Path(config_file)

        # 确保配置目录存在
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

        # 加载配置
        self.config = self._load_config()

        # 配置变更监听器
        self.listeners: List[callable] = []

        self.logger.info(f"配置管理器初始化完成，配置文件: {self.config_file}")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                self.logger.info("配置文件加载成功")
                return self._merge_with_defaults(config)
            except Exception as e:
                self.logger.error(f"配置文件加载失败: {e}")
                return self._get_default_config()
        else:
            self.logger.warning("配置文件不存在，使用默认配置")
            default_config = self._get_default_config()
            self._save_config(default_config)  # 创建默认配置文件
            return default_config

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "app": {
                "name": "文档问答桌面应用",
                "version": "1.0.0",
                "organization": "MySite",
                "ui": {
                    "theme": "light",
                    "language": "zh_CN",
                    "window": {"width": 1200, "height": 800, "maximized": False},
                },
                "data": {
                    "chroma_db_path": "data/chroma_db",
                    "documents_path": "data/documents",
                    "config_path": "config",
                },
            },
            "ai": {
                "openai": {
                    "api_key": "you-key",
                    "model": "GLM-4-Flash",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                },
                "chat": {
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "top_p": 1.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                },
                "context": {
                    "max_history": 10,
                    "include_context_docs": 5,
                    "max_doc_context_length": 2000,
                },
            },
            "document": {
                "supported_extensions": [".pdf", ".docx", ".txt", ".md", ".markdown"],
                "processing": {
                    "max_file_size_mb": 10,
                    "chunk_size": 1000,
                    "chunk_overlap": 200,
                },
                "text": {
                    "encoding": "utf-8",
                    "min_chunk_length": 50,
                    "max_chunk_length": 2000,
                },
            },
            "vector_db": {
                "chroma": {
                    "persist_directory": "data/chroma_db",
                    "collection_name": "document_collection",
                    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
                    "distance_metric": "cosine",
                },
                "search": {
                    "n_results": 5,
                    "include_metadata": True,
                    "include_distances": False,
                },
            },
            "ui_settings": {
                "document_panel": {
                    "default_width": 300,
                    "show_file_size": True,
                    "show_upload_time": True,
                },
                "chat_panel": {
                    "show_timestamps": True,
                    "auto_scroll": True,
                    "max_message_length": 5000,
                },
                "config_panel": {"show_advanced": False, "auto_save": True},
            },
        }

    def _merge_with_defaults(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """将用户配置与默认配置合并"""
        default_config = self._get_default_config()
        return self._deep_merge(default_config, user_config)

    def _deep_merge(
        self, base: Dict[str, Any], update: Dict[str, Any]
    ) -> Dict[str, Any]:
        """深度合并两个字典"""
        result = base.copy()

        for key, value in update.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _save_config(self, config: Dict[str, Any]) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2,
                    sort_keys=False,
                )

            self.logger.info("配置文件保存成功")
            return True

        except Exception as e:
            self.logger.error(f"配置文件保存失败: {e}")
            return False

    def get_config(self, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键路径，如 "ai.openai.api_key"，如果为None返回整个配置
            default: 默认值

        Returns:
            配置值或默认值
        """
        if key is None:
            return self.config

        try:
            value = self.config
            for part in key.split("."):
                value = value[part]
            return value
        except (KeyError, TypeError):
            return default

    def set_config(self, key: str, value: Any, save: bool = True) -> bool:
        """
        设置配置值

        Args:
            key: 配置键路径，如 "ai.openai.api_key"
            value: 配置值
            save: 是否立即保存到文件

        Returns:
            设置是否成功
        """
        try:
            keys = key.split(".")
            config_ref = self.config

            # 导航到父级配置
            for part in keys[:-1]:
                if part not in config_ref:
                    config_ref[part] = {}
                config_ref = config_ref[part]

            # 设置值
            config_ref[keys[-1]] = value

            # 通知监听器
            self._notify_listeners(key, value)

            # 保存到文件
            if save:
                return self.save_config()

            return True

        except Exception as e:
            self.logger.error(f"设置配置失败: {key} = {value}, 错误: {e}")
            return False

    def save_config(self) -> bool:
        """保存当前配置到文件"""
        return self._save_config(self.config)

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """
        更新整个配置

        Args:
            new_config: 新配置

        Returns:
            bool: 更新是否成功
        """
        try:
            self.config = self._deep_merge(self.config, new_config)
            return self.save_config()
        except Exception as e:
            self.logger.error(f"配置更新失败: {e}")
            return False

    def reload_config(self) -> bool:
        """重新加载配置文件"""
        new_config = self._load_config()
        if new_config:
            self.config = new_config
            self.logger.info("配置文件重新加载完成")
            return True
        return False

    def validate_config(self) -> Dict[str, List[str]]:
        """
        验证配置有效性

        Returns:
            包含错误和警告的字典
        """
        errors = []
        warnings = []

        # 验证AI配置
        openai_api_key = self.get_config("ai.openai.api_key")
        if not openai_api_key:
            warnings.append("OpenAI API密钥未配置，将无法使用AI对话功能")

        # 验证数据目录
        data_dirs = [
            self.get_config("app.data.chroma_db_path"),
            self.get_config("app.data.documents_path"),
        ]

        for data_dir in data_dirs:
            try:
                Path(data_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建数据目录 {data_dir}: {e}")

        # 验证UI设置
        window_width = self.get_config("app.ui.window.width")
        window_height = self.get_config("app.ui.window.height")

        if not isinstance(window_width, int) or window_width < 800:
            warnings.append("窗口宽度设置可能过小，建议至少800像素")

        if not isinstance(window_height, int) or window_height < 600:
            warnings.append("窗口高度设置可能过小，建议至少600像素")

        result = {}
        if errors:
            result["errors"] = errors
        if warnings:
            result["warnings"] = warnings

        return result

    def add_listener(self, listener: callable) -> None:
        """
        添加配置变更监听器

        Args:
            listener: 监听器函数，格式为 func(key: str, value: Any)
        """
        if listener not in self.listeners:
            self.listeners.append(listener)
            self.logger.debug(f"添加配置变更监听器，当前总数: {len(self.listeners)}")

    def remove_listener(self, listener: callable) -> None:
        """移除配置变更监听器"""
        if listener in self.listeners:
            self.listeners.remove(listener)
            self.logger.debug(f"移除配置变更监听器，剩余总数: {len(self.listeners)}")

    def _notify_listeners(self, key: str, value: Any) -> None:
        """通知所有监听器配置变更"""
        for listener in self.listeners:
            try:
                listener(key, value)
            except Exception as e:
                self.logger.error(f"配置变更监听器执行失败: {e}")

    def export_config(self, export_path: str) -> bool:
        """
        导出配置到指定文件

        Args:
            export_path: 导出文件路径

        Returns:
            导出是否成功
        """
        try:
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)

            with open(export_file, "w", encoding="utf-8") as f:
                yaml.dump(
                    self.config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    indent=2,
                )

            self.logger.info(f"配置导出成功: {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"配置导出失败: {e}")
            return False

    def import_config(self, import_path: str) -> bool:
        """
        从文件导入配置

        Args:
            import_path: 导入文件路径

        Returns:
            导入是否成功
        """
        try:
            import_file = Path(import_path)
            if not import_file.exists():
                self.logger.error(f"导入文件不存在: {import_path}")
                return False

            with open(import_file, "r", encoding="utf-8") as f:
                imported_config = yaml.safe_load(f)

            if not isinstance(imported_config, dict):
                self.logger.error("导入的配置文件格式无效")
                return False

            # 合并配置
            self.config = self._deep_merge(self.config, imported_config)

            # 保存并通知监听器
            if self.save_config():
                # 通知所有配置项的变更
                for key_path in self._get_all_config_paths(imported_config):
                    value = self.get_config(key_path)
                    self._notify_listeners(key_path, value)

                self.logger.info(f"配置导入成功: {import_path}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"配置导入失败: {e}")
            return False

    def _get_all_config_paths(
        self, config: Dict[str, Any], prefix: str = ""
    ) -> List[str]:
        """获取配置中的所有键路径"""
        paths = []
        for key, value in config.items():
            current_path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                paths.extend(self._get_all_config_paths(value, current_path))
            else:
                paths.append(current_path)
        return paths


def create_config_manager(config_file: Optional[str] = None) -> ConfigManager:
    """
    创建配置管理器实例

    Args:
        config_file: 配置文件路径（可选）

    Returns:
        ConfigManager实例
    """
    return ConfigManager(config_file)
