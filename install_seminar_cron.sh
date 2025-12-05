#!/usr/bin/env bash
set -euo pipefail

# 本脚本将定时执行 run_hku_seminar_sync.sh，用于轮询新的 seminars。
# 使用方式：
#   ./install_seminar_cron.sh               # 默认每 30 分钟运行一次
#   ./install_seminar_cron.sh "0 * * * *"   # 自定义 cron 表达式（例如每小时）
#
# 注意：
# - 脚本会在当前用户的 crontab 里添加（或更新）一条记录；
# - 会自动去重（删除旧的同路径任务，只保留一条最新设置的）。

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_SCRIPT="$SCRIPT_DIR/run_hku_seminar_sync.sh"

if [ ! -x "$RUN_SCRIPT" ]; then
  echo "错误：未找到可执行的 $RUN_SCRIPT" >&2
  echo "请先为 run_hku_seminar_sync.sh 添加执行权限：" >&2
  echo "  chmod +x \"$RUN_SCRIPT\"" >&2
  exit 1
fi

# 默认每 30 分钟执行一次（注意：这里不要带引号）
CRON_SCHEDULE="${1:-*/30 * * * *}"

echo "将为当前用户安装 crontab 条目："
echo "  时间：$CRON_SCHEDULE"
echo "  命令：$RUN_SCRIPT"
echo

# 构造 crontab 行，输出日志到项目目录下
CRON_LINE="$CRON_SCHEDULE $RUN_SCRIPT >> \"$SCRIPT_DIR/seminar_cron.log\" 2>&1"

# 读取当前 crontab，移除已有的同脚本路径条目，然后追加新条目
TMP_FILE="$(mktemp)"
crontab -l 2>/dev/null | grep -v -F "$RUN_SCRIPT" >"$TMP_FILE" || true
echo "$CRON_LINE" >>"$TMP_FILE"
crontab "$TMP_FILE"
rm -f "$TMP_FILE"

echo "已更新当前用户的 crontab。当前条目："
crontab -l | grep -F "$RUN_SCRIPT" || true
