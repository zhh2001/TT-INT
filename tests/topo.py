"""在已进入用户+挂载+网络命名空间的 shell 中搭建 source→transit 链路。

外层 ``run.sh`` 会用 ``unshare -mUrn`` 进入命名空间，并重挂 sysfs，
随后调用本模块创建 veth、启动 simple_switch、写入流表。
"""

from __future__ import annotations

import os
import shlex
import socket
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(cmd: str | list[str], check: bool = True) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return subprocess.run(cmd, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _wait_port(port: int, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"thrift 端口 {port} 在 {timeout}s 内未就绪")


@dataclass
class Switch:
    name: str
    json_path: str
    device_id: int
    thrift_port: int
    ifaces: list[tuple[int, str]]
    log_path: str
    process: subprocess.Popen | None = None
    log_fp: object = field(default=None, repr=False)

    def start(self) -> None:
        cmd = [
            "simple_switch",
            "--device-id", str(self.device_id),
            "--thrift-port", str(self.thrift_port),
            "--log-file", self.log_path + ".bm",
            "--log-flush",
        ]
        for port_no, iface in self.ifaces:
            cmd += ["-i", f"{port_no}@{iface}"]
        cmd += [self.json_path]

        self.log_fp = open(self.log_path, "w")
        self.process = subprocess.Popen(
            cmd, stdout=self.log_fp, stderr=subprocess.STDOUT,
        )
        _wait_port(self.thrift_port)

    def cli(self, script: str) -> None:
        proc = subprocess.run(
            ["simple_switch_CLI", "--thrift-port", str(self.thrift_port)],
            input=script, text=True, capture_output=True, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"simple_switch_CLI 失败 ({self.name}):\n"
                f"stdout={proc.stdout}\nstderr={proc.stderr}"
            )

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        if self.log_fp is not None:
            self.log_fp.close()
            self.log_fp = None


def _make_veth_pair(a: str, b: str) -> None:
    _run(f"ip link add {a} type veth peer name {b}")
    for n in (a, b):
        _run(f"ethtool -K {n} tx off rx off tso off gso off gro off ufo off",
             check=False)
        _run(f"ip link set {n} up")
        _run(f"ip link set {n} mtu 9000")


@dataclass
class Chain:
    rx_iface: str
    tx_iface: str
    s1: Switch
    s2: Switch


@contextmanager
def bmv2_chain(log_dir: str):
    """搭建 host_a -- s1(source) -- s2(transit) -- host_b 的拓扑。"""
    os.makedirs(log_dir, exist_ok=True)

    _make_veth_pair("h_a",   "s1_p1")
    _make_veth_pair("s1_p2", "s2_p1")
    _make_veth_pair("s2_p2", "h_b")

    s1 = Switch(
        name="s1",
        json_path=os.path.join(PROJECT_ROOT, "build/source.json"),
        device_id=0,
        thrift_port=22001,
        ifaces=[(1, "s1_p1"), (2, "s1_p2")],
        log_path=os.path.join(log_dir, "s1.log"),
    )
    s2 = Switch(
        name="s2",
        json_path=os.path.join(PROJECT_ROOT, "build/transit.json"),
        device_id=1,
        thrift_port=22002,
        ifaces=[(1, "s2_p1"), (2, "s2_p2")],
        log_path=os.path.join(log_dir, "s2.log"),
    )

    try:
        s1.start()
        s2.start()
        yield Chain(rx_iface="h_a", tx_iface="h_b", s1=s1, s2=s2)
    finally:
        s1.stop()
        s2.stop()
