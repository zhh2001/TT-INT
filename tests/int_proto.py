"""TT-INT 报文协议定义，供测试解析使用。"""

from scapy.fields import ByteField, FieldLenField, PacketListField
from scapy.packet import Packet, bind_layers
from scapy.layers.inet import IP


PROTO_INT = 0xFD
PROTO_UDP = 0x11


class IntMetadata(Packet):
    name = "IntMetadata"
    fields_desc = [
        ByteField("switch_id", 0),
        ByteField("hop_num",   0),
    ]

    def extract_padding(self, s):
        return b"", s


class IntHeader(Packet):
    name = "IntHeader"
    fields_desc = [
        FieldLenField("count", 0, fmt="B", count_of="metadata"),
        ByteField("init_ttl", 0),
        PacketListField("metadata", [], IntMetadata, count_from=lambda p: p.count),
    ]


bind_layers(IP, IntHeader, proto=PROTO_INT)
