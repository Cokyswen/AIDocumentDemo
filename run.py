"""
应用程序启动脚本
"""

import sys
from pathlib import Path


def main():
    """启动程序主函数"""
    # 验证配置文件存在
    config_path = Path(__file__).parent / "config" / "settings.yaml"
    if not config_path.exists():
        print(f"警告: 配置文件不存在 {config_path}")
        print("将使用默认配置运行")

    # 验证数据目录
    data_dir = Path(__file__).parent / ".chroma_data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "chroma_db").mkdir(exist_ok=True)
    (data_dir / "documents").mkdir(exist_ok=True)
    
    # 确保日志目录存在
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # 导入并运行主应用
    try:
        from main import main as app_main

        return app_main()
    except Exception as e:
        print(f"应用程序启动失败: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
