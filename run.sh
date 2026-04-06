#!/bin/bash
# 文档问答桌面应用程序启动脚本

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
source .venv/bin/activate

# 检查并安装依赖
echo "检查依赖包..."
pip install -r requirements.txt -q

# 启动应用程序
echo "启动文档问答桌面应用..."
python run.py

deactivate
