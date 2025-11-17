#!/usr/bin/env bash
set -euo pipefail

# 切换到脚本所在目录，保证在项目根目录执行
cd "$(dirname "$0")"

# 选择 python 解释器，优先 python3
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3.9+ 未安装，请先安装 Python。" >&2
  exit 1
fi

VENV_DIR=".venv"

# 如果虚拟环境不存在，就创建一个
if [ ! -d "$VENV_DIR" ]; then
  echo "创建虚拟环境：$VENV_DIR ..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

# 激活虚拟环境
# shellcheck source=/dev/null
. "$VENV_DIR/bin/activate"

echo "使用虚拟环境：$VENV_DIR"

# 升级 pip（可选，但通常有用）
pip install --upgrade pip

# 安装依赖
if [ -f "requirements.txt" ]; then
  echo "安装依赖：requirements.txt ..."
  pip install -r requirements.txt
else
  echo "未找到 requirements.txt，无法安装依赖。" >&2
  exit 1
fi

# 运行抓取 + 同步 Outlook 日历的脚本
echo "运行 hku_seminars_to_outlook.py ..."
exec python hku_seminars_to_outlook.py "$@"

