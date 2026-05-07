"""使用 p4-utils + Mininet 搭起 main.py 的 5 交换机拓扑，
端到端验证最基础的时间阈值 INT 行为。

需要 root，由 ``run_mininet.sh`` 通过 sudo 调起。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import build_network                                    # noqa: E402
from scapy.all import Ether, IP, UDP, rdpcap, wrpcap              # noqa: E402

from tests.int_proto import IntHeader, PROTO_INT                  # noqa: E402


SRC_IP   = "10.0.1.1"
DST_IP   = "10.0.5.5"
TIME_TH_US = 100_000              # 100 ms 时间阈值
INIT_TTL = 64

# 与 main.py 中 setThriftPort 保持一致
THRIFT_PORTS = [10001, 10002, 10003, 10004, 10005]


def _cli_write_registers(thrift_port: int) -> None:
    script = (
        f"register_write time_th 0 {TIME_TH_US}\n"
        "register_write last_ts 0 0\n"
        "register_write max_cnt 0 16\n"
    )
    proc = subprocess.run(
        ["simple_switch_CLI", "--thrift-port", str(thrift_port)],
        input=script, text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"simple_switch_CLI port={thrift_port} 失败：\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )


# 在 h1 命名空间内执行：发送三个测试 UDP 数据包
H1_SEND_SCRIPT = r"""
import time
from scapy.all import Ether, IP, UDP, sendp
from scapy.arch import get_if_hwaddr
from scapy.interfaces import get_if_list

iface = next(i for i in get_if_list() if i != "lo")
src_mac = get_if_hwaddr(iface)
dst_mac = "00:01:0a:00:01:01"   # s1 面向 h1 的接口 MAC

def make(tag):
    return (Ether(src=src_mac, dst=dst_mac)
            / IP(src="{src_ip}", dst="{dst_ip}", ttl={ttl})
            / UDP(sport=4321, dport=1234)
            / (bytes([tag]) * 32))

# tag=1：首包
sendp(make(1), iface=iface, verbose=False)
# tag=2：紧随其后，远小于阈值
time.sleep(0.005)
sendp(make(2), iface=iface, verbose=False)
# tag=3：等待超过阈值
time.sleep({wait_after_threshold})
sendp(make(3), iface=iface, verbose=False)
""".format(src_ip=SRC_IP, dst_ip=DST_IP, ttl=INIT_TTL,
           wait_after_threshold=TIME_TH_US / 1_000_000 + 0.1)


def _classify(pkts):
    """按 32 字节连续相同的 payload 段识别 tag。"""
    by_tag: dict[int, list] = {}
    for p in pkts:
        if not p.haslayer(IP):
            continue
        ip = p[IP]
        if ip.src != SRC_IP or ip.dst != DST_IP:
            continue
        raw = bytes(p)
        tag = None
        for i in range(len(raw) - 32, -1, -1):
            seg = raw[i:i + 32]
            if len(seg) == 32 and len(set(seg)) == 1:
                tag = seg[0]
                break
        if tag is not None:
            by_tag.setdefault(tag, []).append(p)
    return by_tag


def _expect_int(pkt, expected_count: int, expected_metadata: list[tuple[int, int]]):
    ip = pkt[IP]
    assert ip.proto == PROTO_INT, f"期望 IP.proto={PROTO_INT:#x}, 实际 {ip.proto:#x}"
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
    assert ip.proto == PROTO_INT, f"期望 IP.proto={PROTO_INT:#x}, 实际 {ip.proto:#x}"
    inth = pkt[IntHeader]
    assert inth.count == 0, f"期望 count=0（阈值内不插入），实际 {inth.count}"
    assert len(inth.metadata) == 0


def run() -> int:
    os.chdir(str(ROOT))

    net = build_network()
    net.disableCli()    # 跑测试时不进 CLI；脚本控制启动/停止
    net.startNetwork()

    try:
        # 让 simple_switch_grpc 完成表项加载
        time.sleep(2.0)

        # 把每台交换机的时间阈值统一改为 100 ms
        for port in THRIFT_PORTS:
            _cli_write_registers(port)

        h1 = net.net.get("h1")

        # 在 h1 命名空间里通过其自带 python 发包
        h1_send = h1.popen(["python3", "-c", H1_SEND_SCRIPT],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = h1_send.communicate(timeout=10)
        if h1_send.returncode != 0:
            raise RuntimeError(
                f"h1 发包脚本失败：rc={h1_send.returncode}\n"
                f"stdout={out.decode()}\nstderr={err.decode()}"
            )

        # 给最后一个数据包足够时间穿过整条链路
        time.sleep(1.0)

        # 读 s5 入向 pcap：此时 INT 还在，sink 还未剥离
        pcap_path = ROOT / "pcap" / "s5" / "s5-eth1_in.pcap"
        if not pcap_path.exists():
            raise FileNotFoundError(f"未生成 pcap：{pcap_path}")

        pkts = rdpcap(str(pcap_path))
        groups = _classify(pkts)

        for tag in (1, 2, 3):
            assert tag in groups and groups[tag], (
                f"未在 {pcap_path.name} 中找到 tag={tag} 的数据包"
            )

        # 链路 h1-s1-s2-s3-s4-s5：4 个会插入元数据的位置
        # 栈顺序：push_front 使最新的位于索引 0
        # 各跳的 hop_num = init_ttl - ipv4.ttl(经过该跳之后)
        first_expected = [(4, 4), (3, 3), (2, 2), (1, 1)]
        _expect_int(groups[1][0], expected_count=4,
                    expected_metadata=first_expected)
        _expect_no_metadata(groups[2][0])
        _expect_int(groups[3][0], expected_count=4,
                    expected_metadata=first_expected)

    finally:
        try:
            net.stopNetwork()
        except AttributeError:
            net.net.stop()

    return 0


if __name__ == "__main__":
    try:
        rc = run()
    except AssertionError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        rc = 1
    except Exception as e:
        import traceback
        traceback.print_exc()
        rc = 2
    if rc == 0:
        print("[PASS] Mininet 端到端：基础时间阈值 INT 行为符合预期")
    sys.exit(rc)
