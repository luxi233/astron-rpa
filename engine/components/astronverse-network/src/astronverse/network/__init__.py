from enum import Enum


class ReportLevelType(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class RequestType(Enum):
    POST = "post"
    GET = "get"
    CONNECT = "connect"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    OPTIONS = "options"
    HEAD = "head"
    TRACE = "trace"


class ListType(Enum):
    ALL = "all"
    FILE = "file"
    FOLDER = "folder"


class FileType(Enum):
    FILE = "file"
    FOLDER = "folder"


class StateType(Enum):
    CREATE = "create"
    ERROR = "error"


class SaveType(Enum):
    YES = "yes"
    NO = "no"


class FileExistenceType(Enum):
    RENAME = "rename"
    OVERWRITE = "overwrite"
    CANCEL = "cancel"


class FtpServerType(Enum):
    FTP = "ftp"  # FTP服务器
    SFTP = "sftp"  # SFTP服务器


class SftpLoginMode(Enum):
    PASSWORD = "password"  # 密码连接
    KEY = "key"  # 密钥连接
