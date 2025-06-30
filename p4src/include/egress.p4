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
    action add_int_metadata(switchId_t swid) {
        if (hdr.int_header.isValid()) {
            // 获取时间差
            timestamp_t last_ts = get_last_ts();
            timestamp_t time_thld = get_time_thld();
            timestamp_t timestamp_delta = standard_metadata.ingress_global_timestamp - last_ts;

            // 是否超过阈值
            if (timestamp_delta >= time_thld || is_bytes_abnormal()) {
                // 将 INT 堆栈计数器增加 1
                hdr.int_header.count = hdr.int_header.count + 1;

                // 追加当前交换机的 INT METADATA
                hdr.int_metadata.push_front(1);
                hdr.int_metadata[0].setValid();
                hdr.int_metadata[0].switch_id = swid;
                hdr.int_metadata[0].output_port = standard_metadata.egress_port;

                if (standard_metadata.instance_type == 0) {
                    // 更新最近一次写入 INT METADATA 的时间戳
                    bool ok = set_last_ts(standard_metadata.ingress_global_timestamp);
                    assert(ok);
                    if (!ok) {}

                    // 进入下一个流量监控窗口
                    new_bytes_window();
                }
            } else {}
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
        if (hdr.int_header.isValid()){
            int_table.apply();
        }

        if (INT_NODE_TYPE == INT_SINK_NODE) {
            if (standard_metadata.instance_type == 0) {
                if (hdr.int_header.isValid()) {
                    // 在 Sink 节点剥离正常数据包上的 INT 信息
                    hdr.ipv4.protocol = PROTO_UDP;
                    hdr.int_header.setInvalid();
                    hdr.int_metadata.pop_front(MAX_INT_METADATA);
                }
            } else if (standard_metadata.instance_type == 1) {
                // 在入口克隆的数据包
                log_msg("克隆数据包经过");

                bit<32> length = 0;
                length = length + HEADER_LENGTH_ETHERNET;
                length = length + HEADER_LENGTH_IPV4;
                length = length + HEADER_LENGTH_INT;
                length = length + (bit<32>)(METADATA_LENGTH_INT * hdr.int_header.count);
                truncate(length);
            } else {}
        }
    }
}

#endif  /* _EGRESS_P4_ */
