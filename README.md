# TT-INT

A Time-Threshold-based Lightweight In-Band Network Telemetry Scheme for
P4-Enabled Programmable Networks.

本仓库提供 TT-INT 论文中"基础时间阈值机制"在 BMv2 上的最小可运行实现，
以及两套自动化测试。

## 仓库结构

```
.
├── p4src/                 P4_16 数据平面
│   ├── source.p4          INT 源节点入口（INT_NODE_TYPE=1）
│   ├── transit.p4         INT 中转节点入口（INT_NODE_TYPE=2）
│   ├── sink.p4            INT 汇聚节点入口（INT_NODE_TYPE=3）
│   └── include/           parser / ingress / egress / deparser / 寄存器
├── commands/              每台交换机启动后下发的 simple_switch_CLI 脚本
├── controllers/           控制面侧脚本占位
├── tools/                 拓扑数据、收发辅助脚本
├── main.py                p4-utils 编排入口（5 交换机直链 + Mininet）
├── tests/
│   ├── run.sh             无 root 的 BMv2 功能测试
│   ├── test_basic.py      上面那条路径的断言主体
│   ├── topo.py            unshare 命名空间内搭 veth + simple_switch
│   ├── int_proto.py       scapy 侧的 INT 头/元数据定义
│   ├── run_mininet.sh     带 sudo 的 Mininet 端到端测试
│   └── test_mininet.py    上面那条路径的断言主体
└── pyproject.toml         uv 管理的测试依赖
```

## 数据平面要点

INT 头：

```
+--------+----------+
| count  | init_ttl |
+--------+----------+
```

INT 元数据栈中每条记录：

```
+-----------+---------+
| switch_id | hop_num |
+-----------+---------+
```

每台交换机维护三个按流索引（`flowId_t`，宽度 `⌈log2 N_FLOW⌉`）的寄存器：

| 寄存器       | 含义                                     |
| ------------ | ---------------------------------------- |
| `time_th`    | 该流的时间阈值（单位：微秒）             |
| `last_ts`    | 该流上次插入遥测元数据的时间戳           |
| `max_cnt`    | 单包允许携带的最大遥测条目数             |

`flow_id_table` 通过 5 元组（当前实现取 `srcAddr` + `dstAddr` 即足够
覆盖测试场景）映射到一个紧凑的 `flow_num`。

`egress` 中的判定逻辑严格按论文 Algorithm 2：

```
delta = ingress_global_timestamp - last_ts[flow_num]
if delta >= time_th[flow_num] && count < max_cnt[flow_num]:
    push (switch_id, init_ttl - ipv4.ttl)
    count += 1
    ipv4.totalLen += METADATA_LENGTH_INT
    last_ts[flow_num] = ingress_global_timestamp
```

Source 节点在 `ingress` 阶段为首次进入 INT 域的数据包安装 INT 头，
并把当时的 IPv4 TTL 写入 `init_ttl`；Sink 节点把整段 INT 信息克隆到
CPU 端口，再从正常转发的数据包中剥离。

## 环境依赖

- p4c 1.2.5+（`p4c-bm2-ss`）
- BMv2（`simple_switch`、`simple_switch_CLI`、`simple_switch_grpc`）
- p4-utils 0.2 + 对应 Mininet（仅 Mininet 路径需要）
- bridge-utils（`enableCpuPort` 调用 `brctl`）
- [uv](https://docs.astral.sh/uv/) 0.11+
- 内核支持非特权 user namespace（运行 `tests/run.sh` 时无需 root）

## 快速开始

### 不需要 root 的 BMv2 功能测试

```
bash tests/run.sh
```

执行流程：

1. 用 `p4c-bm2-ss` 编译 `source.p4` / `transit.p4` / `sink.p4`；
2. `uv sync` 拉起测试用虚拟环境；
3. `unshare -mUrn` 进入用户 + 挂载 + 网络命名空间，重挂 sysfs；
4. 在 ns 内创建 veth 对，串成 `h_a — s1(source) — s2(transit) — h_b`；
5. 启动两台 `simple_switch`，通过 thrift 下发流表与寄存器初值；
6. 顺序发出 3 个 UDP 数据包，验证：
   - 首包：两跳都插入元数据，`count=2`，栈顺序 `[(s2,2), (s1,1)]`；
   - 阈值内的紧随包：两跳都跳过插入，`count=0`；
   - 超出阈值后的下一个包：恢复完整插入，`count=2`。

### 完整 Mininet 端到端测试

```
sudo bash tests/run_mininet.sh
```

复用 `main.build_network()` 起 5 交换机直链
（`h1 — s1 — s2 — s3 — s4 — s5 — h5`），跳过 CLI，
从 `h1` 命名空间内 scapy 发包，读 `pcap/s5/s5-eth1_in.pcap`
（sink 入向、剥离前）做断言。

期望栈顺序为 `[(s4,4), (s3,3), (s2,2), (s1,1)]`。

### 交互式启动整张网络

```
sudo /home/howard/p4dev-python-venv/bin/python main.py
```

会停在 `mininet>` 提示符下，可以 `h1 ping h5`、`pingall` 等。

## 配置时间阈值与最大条数

默认值在 `p4src/include/global.p4` 中：

```c
const timestamp_t DEFAULT_TIME_THRESHOLD = 48w1_000_000;  // 1 s
const bit<8>      DEFAULT_MAX_COUNT      = 8w16;
```

运行时可通过 `simple_switch_CLI` 改写：

```
register_write time_th 0 100000     # 100 ms 阈值（流 0）
register_write max_cnt 0 8          # 单包最多 8 条元数据
```
