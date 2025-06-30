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

    apply {
        if (standard_metadata.instance_type == 0) {
            bool ok = acc_cur_bytes(standard_metadata.packet_length);
            assert(ok);
            if (!ok) {}
        }

        if (hdr.ipv4.isValid()){
            ipv4_lpm.apply();
        }

        if (!hdr.int_header.isValid()) {
            if (hdr.ipv4.protocol != PROTO_CUSTOM) {
                hdr.ipv4.protocol = PROTO_INT;
                hdr.int_header.setValid();
            }
        }

        if (standard_metadata.instance_type == 0) {
            if (INT_NODE_TYPE == INT_SINK_NODE) {
                if (hdr.int_header.isValid()) {
                    clone(CloneType.I2E, 105);
                }
            }
        }
    }
}

#endif  /* _INGRESS_P4_ */
