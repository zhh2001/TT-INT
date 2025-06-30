#ifndef _GLOBAL_P4_
#define _GLOBAL_P4_

#ifndef V1MODEL_VERSION
#define V1MODEL_VERSION 20200408
#endif

#include <core.p4>
#include <v1model.p4>

typedef bit<48> timestamp_t;
typedef bit<32> byteCount_t;

const timestamp_t DEFAULT_TIME_THRESHOLD = 48w1_000_000;  // 时间阈值默认值

register<timestamp_t, bit<1>>(1) time_threshold;  // 时间阈值
register<timestamp_t, bit<1>>(1) last_timestamp;  // 上一次插入遥测信息的时间戳
register<byteCount_t, bit<1>>(2) byte_count;      // 记录最近两个固定时间窗口内的字节累计值，用于判断突发流量

#define INDEX_PREV_BYTES 0  // 上个时间窗口的累计字节数在寄存器中的索引
#define INDEX_CUR_BYTES  1  // 当前时间窗口的累计字节数在寄存器中的索引

/**
 * 获取阈值
 *
 * :return: 时间阈值
 */
timestamp_t get_time_thld() {
    timestamp_t time_thld;
    time_threshold.read(time_thld, 0);

    if (time_thld <= 0) {
        time_thld = DEFAULT_TIME_THRESHOLD;
    }
    return time_thld;
}

/**
 * 获取上一次插入遥测信息的时间戳
 *
 * :return: 上一次插入遥测信息的时间戳
 */
timestamp_t get_last_ts() {
    timestamp_t last_ts;
    last_timestamp.read(last_ts, 0);
    return last_ts;
}

/**
 * 更新最近一次插入遥测信息的时间戳
 *
 * :param last_ts: 上一次插入遥测信息的时间戳
 * :return: 寄存器更新是否成功
 */
bool set_last_ts(in timestamp_t last_ts) {
    if (last_ts <= get_last_ts()) {
        return false;
    } else {
        last_timestamp.write(0, last_ts);
        return true;
    }
}

/**
 * 获取上一个时间窗口的累计字节数
 *
 * :return: 上一个时间窗口的累计字节数
 */
byteCount_t get_prev_bytes() {
    byteCount_t prev_bytes;
    byte_count.read(prev_bytes, INDEX_PREV_BYTES);
    return prev_bytes;
}

/**
 * 获取当前时间窗口的累计字节数
 *
 * :return: 当前时间窗口的累计字节数
 */
byteCount_t get_cur_bytes() {
    byteCount_t cur_bytes;
    byte_count.read(cur_bytes, INDEX_CUR_BYTES);
    return cur_bytes;
}

/**
 * 累加当前时间窗口的累计字节数
 *
 * :param bytes: 新增的字节数
 * :return: 寄存器更新是否成功
 */
bool acc_cur_bytes(in byteCount_t bytes) {
    if (bytes <= 0) {
        return false;
    } else {
        byteCount_t cur_bytes = get_cur_bytes();
        cur_bytes = cur_bytes + bytes;
        byte_count.write(INDEX_CUR_BYTES, cur_bytes);
        return true;
    }
}

/**
 * 判断流量是否突发变大
 *
 * :return: 流量是否突发变大
 */
bool is_bytes_abnormal() {
    // 获取最近两个时间窗口的累计字节数
    byteCount_t prev_bytes = get_prev_bytes();
    byteCount_t cur_bytes = get_cur_bytes();

    // 流量得大于一定的基础值，然后再对比倍数
    if (cur_bytes >= 100 && prev_bytes >= 100 && cur_bytes >= prev_bytes >> 2) {
        return true;
    } else {
        return false;
    }
}

/**
 * 开启新的流量监控窗口
 */
void new_bytes_window() {
    byteCount_t cur_bytes = get_cur_bytes();
    byte_count.write(INDEX_PREV_BYTES, cur_bytes);
    byte_count.write(INDEX_CUR_BYTES, 0);
}

#endif  /* _GLOBAL_P4_ */
