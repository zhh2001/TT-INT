"""在 BMv2 上验证最基础的时间阈值 INT 行为。

拓扑：h_a (10.0.1.1) → s1(source) → s2(transit) → h_b (10.0.5.5)

验证点：
1. 首个数据包：经过 s1、s2 后均插入遥测元数据（count=2，
   元数据顺序为 [s2, s1]，hop_num 与 init_ttl 一致）。
2. 紧随其后的第二个数据包：在时间阈值内到达，两跳均不再插入
   元数据（count=0）。
3. 等待超过阈值后再发送：恢复完整插入（count=2）。
"""

from __future__ import annotations

import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scapy.all import AsyncSniffer, Ether, IP, UDP, sendp  # noqa: E402

from tests.int_proto import IntHeader, PROTO_INT  # noqa: E402
from tests.topo import bmv2_chain                  # noqa: E402


SRC_IP   = "10.0.1.1"
DST_IP   = "10.0.5.5"
SRC_MAC  = "00:00:0a:00:01:01"
DST_MAC  = "00:01:0a:00:01:01"
TIME_TH_US = 100_000  # 100 ms 阈值
INIT_TTL = 64

S1_TABLE_SCRIPT = f"""
table_set_default ipv4_lpm drop
table_set_default int_table add_int_metadata 1
table_add ipv4_lpm ipv4_forward 10.0.5.5/32 => 00:01:0a:00:02:01 2
table_add flow_id_table set_flow_num {SRC_IP} {DST_IP} => 0
register_write time_th 0 {TIME_TH_US}
register_write last_ts 0 0
register_write max_cnt 0 16
"""

S2_TABLE_SCRIPT = f"""
table_set_default ipv4_lpm drop
table_set_default int_table add_int_metadata 2
table_add ipv4_lpm ipv4_forward 10.0.5.5/32 => 00:00:0a:00:05:05 2
table_add flow_id_table set_flow_num {SRC_IP} {DST_IP} => 0
register_write time_th 0 {TIME_TH_US}
register_write last_ts 0 0
register_write max_cnt 0 16
"""


def build_packet(payload_tag: int) -> Ether:
    payload = bytes([payload_tag]) * 32
    return (Ether(src=SRC_MAC, dst=DST_MAC)
            / IP(src=SRC_IP, dst=DST_IP, ttl=INIT_TTL)
            / UDP(sport=4321, dport=1234)
            / payload)


def _classify(pkts):
    """筛选出 src=SRC_IP, dst=DST_IP 的 IP 报文，按 payload tag 分组。

    payload 末尾连续 32 字节相同即为 tag 区，取最后一字节作为 tag。
    """
    by_tag: dict[int, list] = {}
    for p in pkts:
        if not p.haslayer(IP):
            continue
        ip = p[IP]
        if ip.src != SRC_IP or ip.dst != DST_IP:
            continue
        raw = bytes(p)
        # 寻找连续 32 字节相同的尾段作为 tag 标识
        tag = None
        for i in range(len(raw) - 32, -1, -1):
            seg = raw[i:i + 32]
            if len(seg) == 32 and len(set(seg)) == 1:
                tag = seg[0]
                break
        if tag is None:
            continue
        by_tag.setdefault(tag, []).append(p)
    return by_tag


def _expect_int(pkt, expected_count: int, expected_metadata: list[tuple[int, int]]):
    ip = pkt[IP]
    assert ip.proto == PROTO_INT, f"期望 IP.proto=={PROTO_INT:#x}, 实际 {ip.proto:#x}"
    assert pkt.haslayer(IntHeader), "未解析出 IntHeader"
    inth = pkt[IntHeader]
    assert inth.count == expected_count, (
        f"INT count 错误：期望 {expected_count}，实际 {inth.count}"
    )
    assert inth.init_ttl == INIT_TTL, (
        f"init_ttl 错误：期望 {INIT_TTL}，实际 {inth.init_ttl}"
    )
    actual = [(m.switch_id, m.hop_num) for m in inth.metadata]
    assert actual == expected_metadata, (
        f"INT 元数据栈错误：期望 {expected_metadata}，实际 {actual}"
    )


def _expect_no_metadata(pkt):
    ip = pkt[IP]
    assert ip.proto == PROTO_INT, f"期望 IP.proto=={PROTO_INT:#x}, 实际 {ip.proto:#x}"
    inth = pkt[IntHeader]
    assert inth.count == 0, f"期望 count=0（阈值内不插入），实际 {inth.count}"
    assert len(inth.metadata) == 0


def run() -> int:
    log_dir = os.path.join(ROOT, "build", "log")

    with bmv2_chain(log_dir) as chain:
        chain.s1.cli(S1_TABLE_SCRIPT)
        chain.s2.cli(S2_TABLE_SCRIPT)
        rx_iface = chain.rx_iface
        tx_iface = chain.tx_iface

        # AsyncSniffer 在另一个线程持续抓包；start 后短暂停留以确保已就绪
        sniffer = AsyncSniffer(iface=tx_iface, store=True, filter="ip")
        sniffer.start()
        time.sleep(0.3)

        # tag=1：首包，应在两跳都被插入
        sendp(build_packet(1), iface=rx_iface, verbose=False)

        # tag=2：紧随其后，时间差远小于阈值，两跳都应跳过插入
        time.sleep(0.005)
        sendp(build_packet(2), iface=rx_iface, verbose=False)

        # tag=3：等待超过阈值后再发，两跳应再次插入
        time.sleep(TIME_TH_US / 1_000_000 + 0.05)
        sendp(build_packet(3), iface=rx_iface, verbose=False)

        time.sleep(0.5)
        sniffer.stop()

        groups = _classify(sniffer.results)

        for tag in (1, 2, 3):
            assert tag in groups and groups[tag], (
                f"未抓到 tag={tag} 的数据包"
            )

        # 期望首包栈顺序：push_front 使最近插入位于索引 0
        # s1 处 ttl 在 ipv4_forward 中减 1（init_ttl 已先记录），因此 s1 hop_num=1
        # s2 处再减 1，故 s2 hop_num=2
        _expect_int(groups[1][0], expected_count=2, expected_metadata=[(2, 2), (1, 1)])
        _expect_no_metadata(groups[2][0])
        _expect_int(groups[3][0], expected_count=2, expected_metadata=[(2, 2), (1, 1)])

    return 0


if __name__ == "__main__":
    try:
        rc = run()
    except AssertionError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        rc = 1
    except Exception:
        traceback.print_exc()
        rc = 2
    if rc == 0:
        print("[PASS] 基础时间阈值 INT 行为符合预期")
    sys.exit(rc)
