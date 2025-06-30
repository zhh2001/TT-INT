import struct
import warnings

from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI
from scapy.arch import get_if_hwaddr
from scapy.compat import raw
from scapy.fields import ByteField
from scapy.fields import IntField
from scapy.layers.inet import IP
from scapy.layers.inet import UDP
from scapy.layers.l2 import Ether
from scapy.packet import Packet
from scapy.packet import bind_layers
from scapy.sendrecv import sendp
from scapy.sendrecv import sniff

warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

INT_PROTO = 0xFD
CUSTOM_PROTO = 0xFC


class INTHeader(Packet):
    name = "INTHeader"
    fields_desc = [
        ByteField("count", 0),
        ByteField("max_hops", 0)
    ]


class INTMetadata(Packet):
    name = "INTMetadata"
    fields_desc = [
        IntField("raw32", 0)
    ]

    def extract_fields(self):
        switch_id = self.raw32 >> 9
        output_port = self.raw32 & 0x1FF
        return switch_id, output_port


bind_layers(IP, INTHeader, proto=INT_PROTO)


class SinkController:

    def __init__(self, sink_switch_name):
        self.topo = load_topo('topology.json')
        self.sink_switch_name = sink_switch_name
        self.cpu_port = self.topo.get_cpu_port_index(self.sink_switch_name)
        device_id = self.topo.get_p4switch_id(sink_switch_name)
        grpc_port = self.topo.get_grpc_port(sink_switch_name)
        sw_data = self.topo.get_p4rtswitches()[sink_switch_name]
        self.controller = SimpleSwitchP4RuntimeAPI(
            device_id=device_id,
            grpc_port=grpc_port,
            p4rt_path=sw_data['p4rt_path'],
            json_path=sw_data['json_path'],
        )
        self.init()

    def reset(self):
        # 重置 gRPC 服务器
        self.controller.reset_state()

        # 保险一点，通过 ThriftAPI 重置一下
        thrift_port = self.topo.get_thrift_port(self.sink_switch_name)
        controller_thrift = SimpleSwitchThriftAPI(thrift_port, 'localhost')
        controller_thrift.reset_state()

    def init(self):
        self.reset()
        self.add_ipv4_table_entry()
        self.add_clone_session()

    def add_ipv4_table_entry(self):
        # net.enableCpuPort('s5') 导致交换机被重置
        # 这里重新添加一下各个表项
        self.controller.table_set_default('ipv4_lpm', 'drop', [])
        self.controller.table_set_default('int_table', 'add_int_metadata', ['5'])
        self.controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.1.0/24'], ['00:01:0a:00:04:05', '1'])
        self.controller.table_add('ipv4_lpm', 'ipv4_forward', ['10.0.5.5/32'], ['00:00:0a:00:05:05', '2'])

    def add_clone_session(self):
        if self.cpu_port:
            self.controller.cs_create(105, [self.cpu_port])

    def recv_msg_cpu(self, pkt):
        pkt = Ether(raw(pkt))
        if IP in pkt and pkt[IP].proto == INT_PROTO:
            print("\n================ 收到交换机的克隆数据包 ================")
            ip_layer = pkt[IP]
            payload = bytes(ip_layer.payload)

            # --- 1. 解析 INT Header ---
            count = payload[0]
            max_hops = payload[1]
            print(f"[INT] 遥测信息数量：{count}, 剩余可用跳数：{max_hops}")

            # --- 2. 解析每一跳的 INT Metadata ---
            metadata_list = []
            offset = 2  # 起始字节偏移（前2字节是 INT header）

            for i in range(count):
                # 每个 metadata 是 4 字节
                raw_meta = payload[offset:offset + 4]
                if len(raw_meta) < 4:
                    print(f"INT metadata #{i} too short")
                    break

                raw_int = int.from_bytes(raw_meta, byteorder="big")

                switch_id = raw_int >> 9
                output_port = raw_int & 0x1FF
                metadata_list.append((switch_id, output_port))

                print(f"  Hop {count - i}: switch_id={switch_id}, output_port={output_port}")
                offset += 4

            # 3. 解析 UDP Header（剩下的 offset 开始）
            if offset == len(payload):
                print(f"offset={offset}, length={len(payload)}")
                # 发数据包给数据平面
                cpu_port_intf = self.topo.get_cpu_port_intf(self.sink_switch_name, quiet=False)
                src_mac_addr = get_if_hwaddr(cpu_port_intf)
                dst_mac_addr = "ff:ff:ff:ff:ff:ff"
                return_pkt = Ether(src=src_mac_addr, dst=dst_mac_addr)
                return_pkt = return_pkt / IP(dst='10.0.5.5', proto=CUSTOM_PROTO)
                return_pkt = return_pkt / UDP(dport=1234, sport=4321)
                return_pkt = return_pkt / 'From Controller'
                sendp(return_pkt, iface=cpu_port_intf)
                print("=" * 24)
                return

            udp_hdr = payload[offset:offset + 8]
            sport, dport, length, checksum = struct.unpack('!HHHH', udp_hdr)
            print(f"[UDP] {sport} → {dport}, len={length}, checksum=0x{checksum:04x}")
            offset += 8

            # 4. 打印 UDP Payload
            udp_payload = payload[offset:]
            try:
                decoded_payload = udp_payload.decode('utf-8')
                print(f"[UDP Payload] (UTF-8): \"{decoded_payload}\"")
            except UnicodeDecodeError:
                print(f"[UDP Payload] (raw hex): {udp_payload.hex()}")

            print("=" * 24)

    def run_cpu_port_loop(self):
        cpu_port_intf = self.topo.get_cpu_port_intf(self.sink_switch_name, quiet=False).replace("eth0", "eth1")
        sniff(iface=cpu_port_intf,
              prn=lambda packet: self.recv_msg_cpu(packet))


if __name__ == "__main__":
    SinkController('s5').run_cpu_port_loop()
