"""SFTP 适配器: 包装 paramiko.SSHClient/SFTPClient, 模拟 ftplib.FTP 接口, 使 FtpCore 全部静态方法无改动支持 SFTP"""

import ftplib


class SftpAdapter:
    """模拟 ftplib.FTP 接口的 SFTP 适配器(duck-typing, FtpCore/FTP原子无需感知协议差异)

    关键约定:
    - cwd/mkd/delete 等失败时抛 ftplib.error_perm, 保持 FtpCore.is_dir/create_dir 的异常捕获语义
    - nlst() 返回当前目录下的相对名字列表(与 ftplib.nlst 一致)
    - storbinary("STOR name", fp, bufsize)/retrbinary("RETR path", callback, bufsize) 兼容二进制传输
    """

    def __init__(self):
        self._ssh = None
        self._sftp = None
        self._host = None
        self._port = 22
        self.encoding = "utf-8"

    # ---- 连接/登录/关闭 ----

    def connect(self, host, port=22):
        self._host = host
        self._port = int(port) if port else 22

    def login(self, user="", password="", key_path=""):
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = {
            "hostname": self._host,
            "port": self._port,
            "username": user or None,
            "timeout": 30,
            "allow_agent": False,
            "look_for_keys": False,
        }
        if key_path:
            kwargs["pkey"] = self._load_private_key(key_path, password)
            if password:
                kwargs["passphrase"] = password
        else:
            kwargs["password"] = password or None
        ssh.connect(**kwargs)
        self._ssh = ssh
        self._sftp = ssh.open_sftp()

    @staticmethod
    def _load_private_key(key_path, password=""):
        import paramiko

        errors = []
        for key_cls in (
            paramiko.Ed25519Key,
            paramiko.RSAKey,
            paramiko.ECDSAKey,
            paramiko.DSSKey,
        ):
            try:
                return key_cls.from_private_key_file(key_path, password=password or None)
            except Exception as e:
                errors.append("{}: {}".format(key_cls.__name__, e))
        raise ftplib.error_perm("私钥加载失败, 请检查密钥文件格式与口令: {}".format("; ".join(errors)))

    def close(self):
        try:
            if self._sftp:
                self._sftp.close()
        finally:
            if self._ssh:
                self._ssh.close()

    def quit(self):
        self.close()

    def set_debuglevel(self, level):
        pass

    # ---- 目录/文件操作 ----

    def pwd(self):
        cwd = self._sftp.getcwd()
        return cwd if cwd is not None else "/"

    def cwd(self, path):
        try:
            self._sftp.chdir(path)
        except Exception as e:
            raise ftplib.error_perm(str(e))

    def nlst(self):
        try:
            return self._sftp.listdir()
        except Exception as e:
            raise ftplib.error_perm(str(e))

    def rename(self, old_name, new_name):
        try:
            return self._sftp.rename(old_name, new_name)
        except Exception as e:
            raise ftplib.error_perm(str(e))

    def delete(self, name):
        try:
            return self._sftp.remove(name)
        except Exception as e:
            raise ftplib.error_perm(str(e))

    def rmd(self, name):
        try:
            return self._sftp.rmdir(name)
        except Exception as e:
            raise ftplib.error_perm(str(e))

    def mkd(self, name):
        try:
            self._sftp.mkdir(name)
            return name
        except Exception as e:
            raise ftplib.error_perm(str(e))

    # ---- 数据传输 ----

    def storbinary(self, command, fp, bufsize=1024):
        name = command[5:].strip() if command.upper().startswith("STOR") else command
        self._sftp.putfo(fp, name)

    def retrbinary(self, command, callback, bufsize=1024):
        path = command[5:].strip() if command.upper().startswith("RETR") else command
        with self._sftp.open(path, "rb") as remote:
            while True:
                chunk = remote.read(bufsize)
                if not chunk:
                    break
                callback(chunk)

    def retrlines(self, command, callback=None):
        import stat as stat_module

        lines = []
        for attr in sorted(self._sftp.listdir_attr(), key=lambda a: a.filename):
            mode = attr.st_mode or 0
            kind = "d" if stat_module.S_ISDIR(mode) else "-"
            lines.append("{} {:>9} {} {}".format(kind, attr.st_size or 0, attr.filename, ""))
        if callback:
            for line in lines:
                callback(line)
        return lines
