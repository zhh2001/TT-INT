#ifndef _INGRESS_P4_
#define _INGRESS_P4_

#ifndef V1MODEL_VERSION
#define V1MODEL_VERSION 20200408
#endif

#include <core.p4>
#include <v1model.p4>

#include "global.p4"
#include "headers.p4"

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
    action drop() {
        mark_to_drop(standard_metadata);
    }

    action ipv4_forward(macAddr_t dstAddr, egressSpec_t port) {
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        standard_metadata.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    // 将 5 元组映射到一个紧凑的流索引，供 egress 阶段
    // 索引时间阈值/上次插入时间戳/最大条数等寄存器
    action set_flow_num(flowId_t flow_num) {
        meta.flow_num = flow_num;
    }

    table flow_id_table {
        key = {
            hdr.ipv4.srcAddr:  exact;
            hdr.ipv4.dstAddr:  exact;
        }
        actions = {
            set_flow_num;
            NoAction;
        }
        size = N_FLOW;
        default_action = NoAction();
    }

    apply {
#if INT_NODE_TYPE == INT_SOURCE_NODE
        // Source 节点：在转发前为首次进入 INT 域的数据包安装 INT 头，
        // 同时记录初始 TTL，用于后续 hop_num 计算
        if (hdr.ipv4.isValid() && !hdr.int_header.isValid()
                && hdr.ipv4.protocol != PROTO_CUSTOM) {
            hdr.int_header.setValid();
            hdr.int_header.count    = 0;
            hdr.int_header.init_ttl = hdr.ipv4.ttl;
            hdr.ipv4.protocol       = PROTO_INT;
            hdr.ipv4.totalLen       = hdr.ipv4.totalLen + HEADER_LENGTH_INT;
        }
#endif

        if (hdr.ipv4.isValid()) {
            ipv4_lpm.apply();
        }

        if (hdr.int_header.isValid()) {
            flow_id_table.apply();
        }

#if INT_NODE_TYPE == INT_SINK_NODE
        // Sink 节点：将带 INT 信息的数据包克隆到控制平面（CPU 端口）
        if (standard_metadata.instance_type == 0 && hdr.int_header.isValid()) {
            clone(CloneType.I2E, 105);
        }
#endif
    }
}

#endif  /* _INGRESS_P4_ */
