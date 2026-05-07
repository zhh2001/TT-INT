#!/usr/bin/env bash
# 在用户+挂载+网络命名空间内执行 BMv2 功能测试，无需 root。
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p build
p4c-bm2-ss --target bmv2 --arch v1model -o build/source.json  p4src/source.p4
p4c-bm2-ss --target bmv2 --arch v1model -o build/transit.json p4src/transit.p4
p4c-bm2-ss --target bmv2 --arch v1model -o build/sink.json    p4src/sink.p4

uv sync --quiet

# 重挂 sysfs 是因为 libpcap 通过 /sys/class/net 检测网卡，
# 而单纯的 net ns 不会让 /sys 反映新接口
exec unshare -mUrn bash -c '
mount --make-rslave / 2>/dev/null || true
mount -t sysfs sysfs /sys
ip link set lo up
exec .venv/bin/python tests/test_basic.py
'
