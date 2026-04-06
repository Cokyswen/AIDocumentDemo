"""
文档问答桌面应用程序主入口
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from core.config_manager import ConfigManager


def setup_logging():
    """设置应用程序日志"""
    # 确保日志目录存在
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/desktop_app.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """应用程序主函数"""
    # 设置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("启动文档问答桌面应用程序")
    
    # 创建Qt应用
    app = QApplication(sys.argv)
    app.setApplicationName("文档问答桌面应用")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("MySite")
    
    # 应用样式设置
    app.setStyle('Fusion')
    
    # 创建配置管理器
    config_manager = ConfigManager()
    
    try:
        # 创建主窗口
        logger.info("创建主窗口")
        main_window = MainWindow(config_manager)
        main_window.show()
        
        logger.info("应用程序启动完成")
        
        # 运行应用
        return app.exec()
        
    except Exception as e:
        logger.error(f"应用程序启动失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        logger.info("应用程序退出")


if __name__ == "__main__":
    sys.exit(main())