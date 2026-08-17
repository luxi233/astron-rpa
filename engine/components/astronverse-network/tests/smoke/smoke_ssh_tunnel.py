"""M8 SSH隧道冒烟测试：mock SSHTunnelForwarder 验证参数映射与错误分支 + 一条真实失败路径"""
import os
import sys
import tempfile

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-network/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-actionlib/src")

import astronverse.network.ssh_tunnel as st
from astronverse.network import SshLoginMode
from astronverse.network.ssh_tunnel import SshTunnel

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


class MockForwarder:
    fail_start = False
    fail_stop = False
    instances = []

    def __init__(self, ssh_address_or_host, ssh_username=None, ssh_config_file=None,
                 remote_bind_address=None, local_bind_address=None, **kwargs):
        self.ssh_address_or_host = ssh_address_or_host
        self.ssh_username = ssh_username
        self.ssh_config_file = ssh_config_file
        self.remote_bind_address = remote_bind_address
        self.local_bind_address = local_bind_address
        self.auth = kwargs
        self.started = False
        self.stopped = False
        self.local_bind_port = 15432
        MockForwarder.instances.append(self)

    def start(self):
        self.started = True
        if MockForwarder.fail_start:
            raise OSError("connection refused")

    def stop(self):
        self.stopped = True
        if MockForwarder.fail_stop:
            raise RuntimeError("stop error")


# 替换模块内的 SSHTunnelForwarder 为 mock
st.SSHTunnelForwarder = MockForwarder

print("== 1. 密码模式参数映射 ==")
tunnel, port = SshTunnel.open_ssh_tunnel(
    ssh_host="jump.example.com", ssh_port=22, ssh_user="admin", password="secret",
    remote_host="db.internal", remote_port=3306, local_port=0,
)
m = MockForwarder.instances[-1]
check("返回实际本地端口", port == 15432, f"port={port}")
check("跳板地址元组", m.ssh_address_or_host == ("jump.example.com", 22), str(m.ssh_address_or_host))
check("用户名", m.ssh_username == "admin")
check("密码认证", m.auth.get("ssh_password") == "secret" and "ssh_pkey" not in m.auth, str(m.auth))
check("目标转发", m.remote_bind_address == ("db.internal", 3306))
check("本地绑定自动分配", m.local_bind_address == ("127.0.0.1", 0))
check("不读ssh config", m.ssh_config_file is None)
check("已start", m.started and tunnel is m)

print("== 2. 密钥模式参数映射 ==")
keyfile = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
keyfile.write(b"FAKE KEY")
keyfile.close()
tunnel2, port2 = SshTunnel.open_ssh_tunnel(
    ssh_host="jump", ssh_port=2222, ssh_user="ops",
    login_mode=SshLoginMode.KEY, password="keypassphrase", key_path=keyfile.name,
    remote_host="redis.internal", remote_port=6379, local_port=16379,
)
m2 = MockForwarder.instances[-1]
check("密钥认证", m2.auth.get("ssh_pkey") == keyfile.name and "ssh_password" not in m2.auth, str(m2.auth))
check("私钥口令", m2.auth.get("ssh_private_key_password") == "keypassphrase")
check("指定本地端口", m2.local_bind_address == ("127.0.0.1", 16379))

print("== 3. 端口默认值 ==")
SshTunnel.open_ssh_tunnel(ssh_host="j", ssh_port="", ssh_user="u", password="p",
                          remote_host="r", remote_port=80, local_port="")
m3 = MockForwarder.instances[-1]
check("ssh_port空→22", m3.ssh_address_or_host == ("j", 22))
check("local_port空→0自动", m3.local_bind_address == ("127.0.0.1", 0))

print("== 4. 错误分支 ==")
# 注意：ErrorCode.format() 原地污染模板(第二次 format 返回首次插值文本)，
# 同一 FORMAT 的多个错误分支只有第一个能断言完整文本，后续只断言前缀/抛出类型


def expect_err(name, fn, contains):
    try:
        fn()
        check(name, False, "未抛异常")
    except BaseException as e:
        check(name, contains in str(e), f"got: {str(e)[:120]}")


expect_err("目标地址为空(首次format,全文)",
           lambda: SshTunnel.open_ssh_tunnel(ssh_host="j", ssh_port=22, ssh_user="u",
                                             password="p", remote_host="", remote_port=80),
           "目标服务地址为空")
expect_err("目标端口为0(前缀,模板已污染)",
           lambda: SshTunnel.open_ssh_tunnel(ssh_host="j", ssh_port=22, ssh_user="u",
                                             password="p", remote_host="r", remote_port=0),
           "SSH隧道创建失败")
expect_err("密钥模式缺私钥路径(前缀)",
           lambda: SshTunnel.open_ssh_tunnel(ssh_host="j", ssh_port=22, ssh_user="u",
                                             login_mode=SshLoginMode.KEY,
                                             remote_host="r", remote_port=80),
           "SSH隧道创建失败")
expect_err("私钥文件不存在(FILE_EXIST首次,全文)",
           lambda: SshTunnel.open_ssh_tunnel(ssh_host="j", ssh_port=22, ssh_user="u",
                                             login_mode=SshLoginMode.KEY, key_path="/tmp/no_such_key.pem",
                                             remote_host="r", remote_port=80),
           "不存在")
MockForwarder.fail_start = True
expect_err("start失败包装(前缀)",
           lambda: SshTunnel.open_ssh_tunnel(ssh_host="j", ssh_port=22, ssh_user="u",
                                             password="p", remote_host="r", remote_port=80),
           "SSH隧道创建失败")
MockForwarder.fail_start = False

print("== 5. 关闭隧道 ==")
ok = SshTunnel.close_ssh_tunnel(tunnel_instance=tunnel)
check("正常关闭", ok is True and tunnel.stopped)
expect_err("关闭无效对象(无stop方法)", lambda: SshTunnel.close_ssh_tunnel(tunnel_instance="not_a_tunnel"), "SSH隧道关闭失败")
MockForwarder.fail_stop = True
expect_err("stop失败包装(前缀)", lambda: SshTunnel.close_ssh_tunnel(tunnel_instance=tunnel2), "SSH隧道关闭失败")
MockForwarder.fail_stop = False

print("== 6. 真实失败路径(sshtunnel→127.0.0.1:1) ==")
# 恢复真实 SSHTunnelForwarder
import importlib
importlib.reload(st)
try:
    st.SshTunnel.open_ssh_tunnel(
        ssh_host="127.0.0.1", ssh_port=1, ssh_user="u", password="p",
        remote_host="127.0.0.1", remote_port=80, local_port=0,
    )
    check("真实连接失败应抛异常", False, "未抛异常")
except BaseException as e:
    check("真实连接失败包装", "SSH隧道创建失败" in str(e), f"got: {str(e)[:150]}")

os.unlink(keyfile.name)
print(f"\n结果: {PASS} PASS / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
