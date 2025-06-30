#define V1MODEL_VERSION 20200408

#define INT_SOURCE_NODE  1
#define INT_TRANSIT_NODE 2
#define INT_SINK_NODE    3

#define INT_NODE_TYPE 2

#include <core.p4>
#include <v1model.p4>

#include "include/checksum.p4"
#include "include/deparser.p4"
#include "include/egress.p4"
#include "include/global.p4"
#include "include/headers.p4"
#include "include/ingress.p4"
#include "include/parser.p4"

V1Switch(
    p=MyParser(),
    vr=MyVerifyChecksum(),
    ig=MyIngress(),
    eg=MyEgress(),
    ck=MyComputeChecksum(),
    dep=MyDeparser()
) main;
