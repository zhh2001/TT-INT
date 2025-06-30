import sys
import socket
from time import sleep

from scapy.arch import get_if_hwaddr
from scapy.interfaces import get_if_list
from scapy.layers.inet import IP
from scapy.layers.inet import UDP
from scapy.layers.l2 import Ether
from scapy.sendrecv import sendp


def get_if():
    for _iface in get_if_list():
        if "eth0" in _iface:
            return _iface
    exit("没找到 eth0 接口")


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('传递 3 个参数: <目标地址> "<携带消息>" <发送数量>')
        exit(1)

    addr = socket.gethostbyname(sys.argv[1])
    iface = get_if()

    pkt = Ether(src=get_if_hwaddr(iface),
                dst="ff:ff:ff:ff:ff:ff")
    pkt = pkt / IP(dst=addr)
    pkt = pkt / UDP(dport=1234,
                    sport=4321)

    try:
        for i in range(int(sys.argv[3])):
            packet = pkt / f'{i + 1:02d} -- [{sys.argv[2]}]'
            packet.show2()
            sendp(packet, iface=iface)
            sleep(0.382)
        sleep(1.25)
    except KeyboardInterrupt:
        exit('Keyboard Interrupt')
