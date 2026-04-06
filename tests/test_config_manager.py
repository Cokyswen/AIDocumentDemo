"""
配置管理器的单元测试
"""

import pytest

from core.config_manager import ConfigManager


class TestConfigManager:
    """配置管理器测试类"""

    def test_config_manager_initialization(self):
        """测试配置管理器初始化"""
        config_manager = ConfigManager()

        assert hasattr(config_manager, "config")
        assert isinstance(config_manager.config, dict)
        assert "ai" in config_manager.config

    def test_get_config(self):
        """测试获取完整配置"""
        config_manager = ConfigManager()
        config = config_manager.get_config()

        assert isinstance(config, dict)
        assert "ai" in config

    def test_get_config_by_key(self):
        """测试通过键获取配置"""
        config_manager = ConfigManager()

        api_key = config_manager.get_config("ai.openai.api_key")
        assert api_key is not None

    def test_get_config_with_default(self):
        """测试获取配置使用默认值"""
        config_manager = ConfigManager()

        value = config_manager.get_config("nonexistent.key", default="default")
        assert value == "default"

    def test_set_config(self):
        """测试设置配置"""
        config_manager = ConfigManager()

        config_manager.set_config("ai.chat.temperature", 0.9, save=False)
        value = config_manager.get_config("ai.chat.temperature")
        assert value == 0.9

    def test_save_config(self):
        """测试保存配置"""
        config_manager = ConfigManager()

        config_manager.set_config("test.key", "test_value", save=False)
        result = config_manager.save_config()
        assert result is True

    def test_reload_config(self):
        """测试重新加载配置"""
        config_manager = ConfigManager()

        # 修改并保存
        config_manager.set_config("ai.chat.temperature", 0.8)

        # 重新加载
        result = config_manager.reload_config()
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
