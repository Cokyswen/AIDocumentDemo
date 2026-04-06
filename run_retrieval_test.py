"""
检索对比测试界面 - 独立运行版本

用于对比不同检索方式的效果
快捷键: Ctrl+R (从主窗口打开)

使用方法:
    python run_retrieval_test.py
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 确保日志目录存在
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("检索对比测试")
    app.setOrganizationName("MySite")

    window = RetrievalTestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
