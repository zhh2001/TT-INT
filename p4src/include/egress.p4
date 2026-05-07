#ifndef _EGRESS_P4_
#define _EGRESS_P4_

#ifndef V1MODEL_VERSION
#define V1MODEL_VERSION 20200408
#endif

#include <core.p4>
#include <v1model.p4>

#include "global.p4"
#include "headers.p4"

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    // 时间阈值驱动的遥测插入逻辑
    action add_int_metadata(switchId_t swid) {
        timestamp_t now    = standard_metadata.ingress_global_timestamp;
        timestamp_t last   = get_last_ts(meta.flow_num);
        timestamp_t thld   = get_time_th(meta.flow_num);
        timestamp_t delta  = now - last;

        // 仅在距离上次插入足够久、且 INT 栈未达上限时才插入
        if (delta >= thld) {
            bit<8> cnt     = hdr.int_header.count;
            bit<8> max_n   = get_max_cnt(meta.flow_num);

            if (cnt < max_n) {
                hdr.int_header.count = cnt + 1;

                hdr.int_metadata.push_front(1);
                hdr.int_metadata[0].setValid();
                hdr.int_metadata[0].switch_id = swid;
                hdr.int_metadata[0].hop_num   = hdr.int_header.init_ttl - hdr.ipv4.ttl;

                hdr.ipv4.totalLen = hdr.ipv4.totalLen + METADATA_LENGTH_INT;

                // 仅对正常转发的数据包更新时间戳，避免克隆数据包重复触发
                if (standard_metadata.instance_type == 0) {
                    set_last_ts(meta.flow_num, now);
                }
            }
        }
    }

    table int_table {
        actions = {
            add_int_metadata;
            NoAction;
        }
        default_action = NoAction();
    }

    apply {
        if (hdr.int_header.isValid()) {
            int_table.apply();
        }

#if INT_NODE_TYPE == INT_SINK_NODE
        if (standard_metadata.instance_type == 0) {
            // 正常转发：从外发数据包中剥离 INT 信息，并把 IP 长度还原
            if (hdr.int_header.isValid()) {
                bit<16> int_bytes = (bit<16>)HEADER_LENGTH_INT
                    + (bit<16>)METADATA_LENGTH_INT * (bit<16>)hdr.int_header.count;
                hdr.ipv4.totalLen = hdr.ipv4.totalLen - int_bytes;
                hdr.ipv4.protocol = PROTO_UDP;
                hdr.int_header.setInvalid();
                hdr.int_metadata.pop_front(MAX_INT_METADATA);
            }
        } else if (standard_metadata.instance_type == 1) {
            // 入口克隆数据包：截断到 INT 元数据末尾，仅保留遥测内容
            bit<32> length = 0;
            length = length + HEADER_LENGTH_ETHERNET;
            length = length + HEADER_LENGTH_IPV4;
            length = length + HEADER_LENGTH_INT;
            length = length + (bit<32>)(METADATA_LENGTH_INT * hdr.int_header.count);
            truncate(length);
        }
#endif
    }
}

#endif  /* _EGRESS_P4_ */
