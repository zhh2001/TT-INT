import os
import pathlib
import warnings

from p4utils.mininetlib.network_API import NetworkAPI

warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings('ignore', category=SyntaxWarning)


def build_network() -> NetworkAPI:
    """组装 5 交换机直链拓扑：h1 - s1 - s2 - s3 - s4 - s5 - h5。

    s1 为 INT Source，s2/s3/s4 为 INT Transit，s5 为 INT Sink。
    返回未启动的 NetworkAPI 实例，由调用方决定是否开 CLI、何时启动。
    """
    net = NetworkAPI()

    net.setCompiler(p4rt=True)

    net.addP4RuntimeSwitch('s1')
    net.addP4RuntimeSwitch('s2')
    net.addP4RuntimeSwitch('s3')
    net.addP4RuntimeSwitch('s4')
    net.addP4RuntimeSwitch('s5')

    net.setP4Source('s1', 'p4src/source.p4')
    net.setP4Source('s2', 'p4src/transit.p4')
    net.setP4Source('s3', 'p4src/transit.p4')
    net.setP4Source('s4', 'p4src/transit.p4')
    net.setP4Source('s5', 'p4src/sink.p4')

    cmd_path = pathlib.Path('')
    cmd_path = cmd_path.joinpath('commands')
    s1_cmd_path = cmd_path.joinpath('s1.sh')
    s2_cmd_path = cmd_path.joinpath('s2.sh')
    s3_cmd_path = cmd_path.joinpath('s3.sh')
    s4_cmd_path = cmd_path.joinpath('s4.sh')
    s5_cmd_path = cmd_path.joinpath('s5.sh')

    net.setP4CliInput('s1', str(s1_cmd_path))
    net.setP4CliInput('s2', str(s2_cmd_path))
    net.setP4CliInput('s3', str(s3_cmd_path))
    net.setP4CliInput('s4', str(s4_cmd_path))
    net.setP4CliInput('s5', str(s5_cmd_path))

    switch_id = 0
    s1_switch_id = switch_id + 1
    s2_switch_id = s1_switch_id + 1
    s3_switch_id = s2_switch_id + 1
    s4_switch_id = s3_switch_id + 1
    s5_switch_id = s4_switch_id + 1

    net.setP4SwitchId('s1', s1_switch_id)
    net.setP4SwitchId('s2', s2_switch_id)
    net.setP4SwitchId('s3', s3_switch_id)
    net.setP4SwitchId('s4', s4_switch_id)
    net.setP4SwitchId('s5', s5_switch_id)

    grpc_port = 50000
    s1_grpc_port = grpc_port + 1
    s2_grpc_port = s1_grpc_port + 1
    s3_grpc_port = s2_grpc_port + 1
    s4_grpc_port = s3_grpc_port + 1
    s5_grpc_port = s4_grpc_port + 1

    net.setGrpcPort('s1', s1_grpc_port)
    net.setGrpcPort('s2', s2_grpc_port)
    net.setGrpcPort('s3', s3_grpc_port)
    net.setGrpcPort('s4', s4_grpc_port)
    net.setGrpcPort('s5', s5_grpc_port)

    thrift_port = 10000
    s1_thrift_port = thrift_port + 1
    s2_thrift_port = s1_thrift_port + 1
    s3_thrift_port = s2_thrift_port + 1
    s4_thrift_port = s3_thrift_port + 1
    s5_thrift_port = s4_thrift_port + 1

    net.setThriftPort('s1', s1_thrift_port)
    net.setThriftPort('s2', s2_thrift_port)
    net.setThriftPort('s3', s3_thrift_port)
    net.setThriftPort('s4', s4_thrift_port)
    net.setThriftPort('s5', s5_thrift_port)

    net.addHost('h1')
    net.addHost('h5')

    net.addLink('h1', 's1')
    net.addLink('s1', 's2')
    net.addLink('s2', 's3')
    net.addLink('s3', 's4')
    net.addLink('s4', 's5')
    net.addLink('s5', 'h5')

    net.mixed()

    net.setIntfPort('h1', 's1', 0)
    net.setIntfPort('s1', 'h1', 1)
    net.setIntfPort('s1', 's2', 2)
    net.setIntfPort('s2', 's1', 1)
    net.setIntfPort('s2', 's3', 2)
    net.setIntfPort('s3', 's2', 1)
    net.setIntfPort('s3', 's4', 2)
    net.setIntfPort('s4', 's3', 1)
    net.setIntfPort('s4', 's5', 2)
    net.setIntfPort('s5', 's4', 1)
    net.setIntfPort('s5', 'h5', 2)
    net.setIntfPort('h5', 's5', 0)

    net.setIntfMac('h1', 's1', '00:00:0a:00:01:01')
    net.setIntfMac('h5', 's5', '00:00:0a:00:05:05')
    net.setIntfMac('s1', 'h1', '00:01:0a:00:01:01')
    net.setIntfMac('s5', 'h5', '00:01:0a:00:05:05')

    net.setIntfMac('s2', 's1', '00:01:0a:00:02:01')
    net.setIntfMac('s2', 's3', '00:01:0a:00:02:03')
    net.setIntfMac('s3', 's2', '00:01:0a:00:03:02')
    net.setIntfMac('s3', 's4', '00:01:0a:00:03:04')
    net.setIntfMac('s4', 's3', '00:01:0a:00:04:03')
    net.setIntfMac('s4', 's5', '00:01:0a:00:04:05')

    net.setIntfMac('s1', 's2', '00:01:0a:00:01:02')
    net.setIntfMac('s3', 's2', '00:01:0a:00:03:02')
    net.setIntfMac('s2', 's3', '00:01:0a:00:02:03')
    net.setIntfMac('s4', 's3', '00:01:0a:00:04:03')
    net.setIntfMac('s3', 's4', '00:01:0a:00:03:04')
    net.setIntfMac('s5', 's4', '00:01:0a:00:05:04')

    net.setIntfIp('h1', 's1', '10.0.1.1/24')
    net.setIntfIp('h5', 's5', '10.0.5.5/24')

    net.setTopologyFile('./topology.json')
    net.setLogLevel('info')

    os.makedirs('./log/s1', mode=0o777, exist_ok=True)
    os.makedirs('./log/s2', mode=0o777, exist_ok=True)
    os.makedirs('./log/s3', mode=0o777, exist_ok=True)
    os.makedirs('./log/s4', mode=0o777, exist_ok=True)
    os.makedirs('./log/s5', mode=0o777, exist_ok=True)

    os.makedirs('./pcap/s1', mode=0o777, exist_ok=True)
    os.makedirs('./pcap/s2', mode=0o777, exist_ok=True)
    os.makedirs('./pcap/s3', mode=0o777, exist_ok=True)
    os.makedirs('./pcap/s4', mode=0o777, exist_ok=True)
    os.makedirs('./pcap/s5', mode=0o777, exist_ok=True)

    net.enableLogAll()
    net.enableLog('s1', './log/s1')
    net.enableLog('s2', './log/s2')
    net.enableLog('s3', './log/s3')
    net.enableLog('s4', './log/s4')
    net.enableLog('s5', './log/s5')

    net.enablePcapDumpAll()
    net.enablePcapDump('s1', './pcap/s1')
    net.enablePcapDump('s2', './pcap/s2')
    net.enablePcapDump('s3', './pcap/s3')
    net.enablePcapDump('s4', './pcap/s4')
    net.enablePcapDump('s5', './pcap/s5')

    net.enableCpuPort('s5')  # 会导致交换机状态重置，流表被清空，很坑！

    return net


def main():
    net = build_network()
    net.enableCli()
    net.startNetwork()


if __name__ == '__main__':
    main()
