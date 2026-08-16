"""应用上下文核心模块: 自定义数据持久化 + 应用参数获取 + 资源文件定位"""


def _get_executor_config():
    """获取执行器全局配置(仅执行器进程内可用), 非执行器环境返回None"""
    try:
        from astronverse.executor.config import Config

        return Config
    except Exception:
        return None


def get_project_id() -> str:
    """获取当前运行的应用(工程)ID, 非执行器环境返回global"""
    config = _get_executor_config()
    if config and getattr(config, "project_id", ""):
        return str(config.project_id)
    return "global"


def get_exec_id() -> str:
    """获取当前执行ID"""
    config = _get_executor_config()
    if config:
        return str(getattr(config, "exec_id", "") or "")
    return ""


def get_project_name() -> str:
    """获取当前运行的应用名称(从生成的package.json读取)"""
    config = _get_executor_config()
    if config:
        import json
        import os

        package_json = os.path.join(getattr(config, "gen_core_path", ""), "package.json")
        if os.path.exists(package_json):
            try:
                with open(package_json, encoding="utf-8") as f:
                    return json.load(f).get("project_info", {}).get("project_name", "")
            except Exception:
                return ""
    return ""


def get_resource_dir() -> str:
    """获取资源文件目录(执行器启动时通过--resource_dir指定, 默认当前目录)"""
    config = _get_executor_config()
    if config:
        return str(getattr(config, "resource_dir", "./") or "./")
    return "./"


def get_run_log_file() -> str:
    """获取当前执行的运行日志文件路径({log_path}/report/{project_id}/{exec_id}.txt), 不存在返回空串"""
    import os

    config = _get_executor_config()
    if config:
        path = os.path.join(
            str(getattr(config, "log_path", "./logs/") or "./logs/"),
            "report",
            str(getattr(config, "project_id", "") or ""),
            "{}.txt".format(getattr(config, "exec_id", "") or ""),
        )
        if os.path.isfile(path):
            return path
    return ""


def format_run_log(log_file: str) -> str:
    """读取JSONL运行日志并转为可读文本"""
    import json
    import time

    lines_out = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                lines_out.append(line)
                continue
            data = entry.get("data", {}) or {}
            log_type = str(data.get("log_type", ""))
            msg = data.get("msg_str", data.get("msg", ""))
            process_id = str(data.get("process_id", ""))
            if not msg:
                msg = json.dumps(data, ensure_ascii=False)
            event_time = entry.get("event_time", 0)
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event_time)) if event_time else ""
            prefix = "{} [{}]".format(time_str, log_type) if log_type else time_str
            suffix = " (流程:{})".format(process_id) if process_id else ""
            lines_out.append("{} {}{}".format(prefix, msg, suffix))
    return "\n".join(lines_out)


# ------------------------- 自定义数据(key-value持久化) -------------------------

CUSTOM_DATA_MAX_LEN = 20000  # 与影刀一致: 单条数据最大20000字符
_CUSTOM_DATA_DIR = "~/.astron/custom_data"


def _custom_data_file() -> str:
    import os

    directory = os.path.expanduser(os.path.join(_CUSTOM_DATA_DIR, "{}.json".format(get_project_id())))
    return directory


def _load_custom_data() -> dict:
    import json
    import os

    path = _custom_data_file()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_custom_data(key: str, content: str) -> None:
    """保存自定义数据(同一应用内同Key覆盖), 单条最大20000字符"""
    import json
    import os

    if len(content) > CUSTOM_DATA_MAX_LEN:
        raise ValueError("自定义数据超过最大长度限制({}字符)".format(CUSTOM_DATA_MAX_LEN))
    data = _load_custom_data()
    data[key] = content
    path = _custom_data_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_custom_data(key: str):
    """读取自定义数据, 未保存过返回None"""
    return _load_custom_data().get(key, None)


# ------------------------- 资源文件 -------------------------


def resolve_resource_path(file_name: str) -> str:
    """解析资源文件绝对路径(校验: 禁止绝对路径与..穿越, 文件必须存在)"""
    import os

    if not file_name:
        raise ValueError("资源文件名不能为空")
    if os.path.isabs(file_name) or ".." in file_name.replace("\\", "/").split("/"):
        raise ValueError("资源文件名仅支持相对路径: {}".format(file_name))
    full_path = os.path.abspath(os.path.join(get_resource_dir(), file_name))
    if not os.path.isfile(full_path):
        raise FileNotFoundError("资源文件不存在: {}".format(file_name))
    return full_path
