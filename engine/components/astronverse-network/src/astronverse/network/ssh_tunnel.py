from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.network import SshLoginMode
from astronverse.network.error import *
from astronverse.network.utils import file_is_exist
from sshtunnel import SSHTunnelForwarder


class SshTunnel:
    @staticmethod
    @atomicMg.atomic(
        "Network",
        inputList=[
            atomicMg.param("ssh_host", types="Str", required=True),
            atomicMg.param("ssh_port", types="Int", required=False),
            atomicMg.param("ssh_user", types="Str", required=False),
            atomicMg.param("login_mode", required=False),
            atomicMg.param(
                "password",
                types="Str",
                required=False,
            ),
            atomicMg.param(
                "key_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"filters": [], "file_type": "file"},
                ),
                dynamics=[
                    DynamicsItem(
                        key="$this.key_path.show",
                        expression="return $this.login_mode.value == '{}'".format(SshLoginMode.KEY.value),
                    )
                ],
                required=False,
            ),
            atomicMg.param("remote_host", types="Str", required=True),
            atomicMg.param("remote_port", types="Int", required=True),
            atomicMg.param("local_port", types="Int", required=False),
        ],
        outputList=[
            atomicMg.param("tunnel_instance", types="Any"),
            atomicMg.param("local_bind_port", types="Int"),
        ],
    )
    def open_ssh_tunnel(
        ssh_host: str,
        ssh_port: int,
        ssh_user: str,
        login_mode: SshLoginMode = SshLoginMode.PASSWORD,
        password: str = "",
        key_path: str = "",
        remote_host: str = "",
        remote_port: int = 0,
        local_port: int = 0,
    ):
        """
        创建SSH隧道(通过跳板机端口转发访问目标服务)
        :param ssh_host: 跳板机地址
        :param ssh_port: 跳板机SSH端口(常用22)
        :param ssh_user: 跳板机用户名
        :param login_mode: 登录方式: 密码连接/密钥连接
        :param password: 密码(密钥连接时为私钥口令, 可为空)
        :param key_path: 私钥文件路径(密钥连接时必填)
        :param remote_host: 目标服务地址(跳板机可达)
        :param remote_port: 目标服务端口
        :param local_port: 本地监听端口(为空或0时自动分配)
        :return: (隧道对象, 实际本地端口)
        """
        if ssh_port is None or ssh_port == "":
            ssh_port = 22
        if local_port is None or local_port == "":
            local_port = 0
        if not remote_host:
            raise BaseException(
                SSH_TUNNEL_OPEN_FORMAT.format("目标服务地址为空"),
                "SSH隧道创建失败，请填写目标服务地址",
            )
        if remote_port is None or remote_port == "" or int(remote_port) <= 0:
            raise BaseException(
                SSH_TUNNEL_OPEN_FORMAT.format("目标服务端口为空"),
                "SSH隧道创建失败，请填写目标服务端口",
            )

        auth_kwargs = {}
        if login_mode == SshLoginMode.KEY:
            if not key_path:
                raise BaseException(
                    SSH_TUNNEL_OPEN_FORMAT.format("密钥连接未指定私钥文件路径"),
                    "SSH隧道创建失败，密钥连接必须指定私钥文件路径",
                )
            if not file_is_exist(key_path):
                raise BaseException(
                    FILE_EXIST_FORMAT.format(key_path),
                    "私钥文件不存在，请检查文件路径信息",
                )
            auth_kwargs["ssh_pkey"] = key_path
            if password:
                auth_kwargs["ssh_private_key_password"] = password
        else:
            auth_kwargs["ssh_password"] = password or ""

        try:
            tunnel = SSHTunnelForwarder(
                (ssh_host, int(ssh_port)),
                ssh_username=ssh_user or "",
                ssh_config_file=None,
                remote_bind_address=(remote_host, int(remote_port)),
                local_bind_address=("127.0.0.1", int(local_port)),
                **auth_kwargs,
            )
            tunnel.start()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SSH_TUNNEL_OPEN_FORMAT.format(e), "SSH隧道创建失败，请检查跳板机与目标服务信息")

        return tunnel, tunnel.local_bind_port

    @staticmethod
    @atomicMg.atomic(
        "Network",
        inputList=[
            atomicMg.param("tunnel_instance", types="Any"),
        ],
        outputList=[
            atomicMg.param("close_tunnel", types="Bool"),
        ],
    )
    def close_ssh_tunnel(tunnel_instance):
        """
        关闭SSH隧道
        :param tunnel_instance: open_ssh_tunnel返回的隧道对象
        :return: 是否成功关闭
        """
        if tunnel_instance is None:
            raise BaseException(
                SSH_TUNNEL_CLOSE_FORMAT.format("隧道对象为空"),
                "SSH隧道关闭失败，请传入open_ssh_tunnel返回的隧道对象",
            )
        try:
            tunnel_instance.stop()
            return True
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SSH_TUNNEL_CLOSE_FORMAT.format(e), "SSH隧道关闭失败")
