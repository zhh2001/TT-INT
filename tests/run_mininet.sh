#!/usr/bin/env bash
# 在系统级 Mininet + p4-utils 环境下端到端验证 TT-INT。
# 需要 root：本脚本以 sudo 运行。
set -euo pipefail

cd "$(dirname "$0")/.."

# 首次运行时清掉残留的 mininet 状态
mn -c >/dev/null 2>&1 || true
rm -rf log pcap topology.json

# p4-utils/Mininet 装在系统已存在的 venv 中；用它的 python 跑
VENV_PY=/home/howard/p4dev-python-venv/bin/python
if [ ! -x "$VENV_PY" ]; then
    echo "未找到 p4-utils 的 python：$VENV_PY" >&2
    exit 1
fi

exec "$VENV_PY" tests/test_mininet.py
