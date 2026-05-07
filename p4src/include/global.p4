#ifndef _GLOBAL_P4_
#define _GLOBAL_P4_

#ifndef V1MODEL_VERSION
#define V1MODEL_VERSION 20200408
#endif

#include <core.p4>
#include <v1model.p4>

#include "headers.p4"

typedef bit<48> timestamp_t;

// 时间阈值与每包最大遥测条数的默认值
const timestamp_t DEFAULT_TIME_THRESHOLD = 48w1_000_000;  // 默认 1s（单位：微秒）
const bit<8>      DEFAULT_MAX_COUNT      = 8w16;

// 按流维度组织的状态寄存器
//   time_th    : 每个流的时间阈值
//   last_ts    : 每个流上一次插入遥测信息的时间戳
//   max_cnt    : 每个流允许携带的最大遥测条目数
register<timestamp_t, flowId_t>(N_FLOW) time_th;
register<timestamp_t, flowId_t>(N_FLOW) last_ts;
register<bit<8>,      flowId_t>(N_FLOW) max_cnt;

/**
 * 获取指定流的时间阈值
 *
 * :param flow_num: 流索引
 * :return: 该流当前生效的时间阈值
 */
timestamp_t get_time_th(in flowId_t flow_num) {
    timestamp_t v;
    time_th.read(v, flow_num);
    if (v == 0) {
        v = DEFAULT_TIME_THRESHOLD;
    }
    return v;
}

/**
 * 获取指定流上一次插入遥测信息的时间戳
 */
timestamp_t get_last_ts(in flowId_t flow_num) {
    timestamp_t v;
    last_ts.read(v, flow_num);
    return v;
}

/**
 * 更新指定流上一次插入遥测信息的时间戳
 */
void set_last_ts(in flowId_t flow_num, in timestamp_t ts) {
    last_ts.write(flow_num, ts);
}

/**
 * 获取指定流允许携带的最大遥测条目数
 */
bit<8> get_max_cnt(in flowId_t flow_num) {
    bit<8> v;
    max_cnt.read(v, flow_num);
    if (v == 0) {
        v = DEFAULT_MAX_COUNT;
    }
    return v;
}

#endif  /* _GLOBAL_P4_ */
