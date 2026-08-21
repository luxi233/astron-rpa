import logging


class Config:
    # 主进程监端口
    VISION_PICKER_PORT = None
    # 服务启动端口开始端
    LOCAL_PORT_START = 32000
    # 本地日志文件
    LOG_BASE_DIR = "logs"
    # log日志等级
    LOG_LEVEL = logging.DEBUG
    # 高亮程序端口号
    HIGHLIGHT_SOCKET_PORT = 11001
    # 元素唯一性校验相似度阈值(可配置)
    UNIQUE_MATCH_SIMILARITY = 0.95
    REMOTE_ADDR = None
