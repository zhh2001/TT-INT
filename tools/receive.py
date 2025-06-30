import sys

from scapy.interfaces import get_if_list
from scapy.layers.http import HTTP
from scapy.layers.inet import ICMP
from scapy.layers.inet import IP
from scapy.layers.inet import IPOption
from scapy.layers.inet import TCP
from scapy.layers.inet import UDP
from scapy.layers.l2 import Ether
from scapy.packet import Packet
from scapy.sendrecv import sniff
from scapy.utils import hexdump

INT_PROTO = 0xFD
CUSTOM_PROTO = 0xFC
UDP_PROTO = 0x11
TCP_PROTO = 0x06
ST_PROTO = 0x05  # Stream
IPv4_PROTO = 0x04  # encapsulation
GGP_PROTO = 0x03
IGMP_PROTO = 0x02  # 组播
ICMP_PROTO = 0x01  # Internet Control
HOPOPT_PROTO = 0x00  # IPv6 Hop-by-Hop


def handle_pkt(pkt):
    print("收到数据包")

    # 如果是我们的自定义协议，则修改为 UDP 协议
    if IP in pkt and pkt[IP].proto == CUSTOM_PROTO:
        print("\n检测到 CUSTOM_PROTO 包，尝试修改为 UDP 协议...")
        pkt[IP].proto = UDP_PROTO
        del pkt[IP].chksum  # 清除校验和，重新计算
        if UDP in pkt:
            del pkt[UDP].chksum

    hexdump(pkt)
    pkt.show2()
    sys.stdout.flush()


def main():
    iface = None
    for _iface in get_if_list():
        if "eth0" in _iface:
            iface = _iface
            break
    if iface is None:
        exit("没找到 eth0 接口")
    print(f"嗅探 {iface}")
    sys.stdout.flush()
    sniff(
        iface=iface,
        prn=handle_pkt,
    )


if __name__ == "__main__":
    main()
