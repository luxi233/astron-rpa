"""astronverse-executor 单测共享 fixtures。

执行器的代码生成链路(Lexer/Parser/AST/Param/Storage 合并)与 bdb 行映射均无平台依赖,
可直接在 macOS 上单测; 用内存 FakeStorage 替换 HttpStorage 避免访问网关。

运行: cd engine && uv run --with pytest pytest servers/astronverse-executor/tests -q
"""

from types import SimpleNamespace

from astronverse.executor.flow.flow import Flow
from astronverse.executor.flow.flow_svc import FlowSvc

PROJECT_ID = "proj_test"
PROCESS_ID = "proc_main"


class FakeStorage:
    """内存存储桩: 替换 HttpStorage, 隔离网关 HTTP 调用"""

    def __init__(self, flow_list=None, param_list=None):
        self._flow_list = flow_list or []
        self._param_list = param_list or []

    def project_info(self, project_id, mode, version=""):
        return {"name": "测试机器人"}

    def process_list(self, project_id, mode, version):
        return []

    def process_detail(self, project_id, mode, version, process_id):
        return self._flow_list

    def module_detail(self, project_id, mode, version, module_id):
        return ""

    def param_list(self, project_id, mode, version, process_id="", module_id=""):
        return self._param_list

    def global_list(self, project_id, mode, version=""):
        return []

    def component_list(self, project_id, mode, version=""):
        return []

    def pip_list(self, project_id, mode, version=""):
        return []

    def smart_component_detail(self, project_id, smart_id, smart_version, mode, version=""):
        return {}


def make_conf(debug_mode: bool = False):
    """独立的 conf 命名空间, 避免污染全局 Config 类属性"""
    return SimpleNamespace(
        debug_mode=debug_mode,
        indentation=" " * 4,
        gateway_port=0,
        main_process_name="主流程",
        is_custom_component=False,
    )


def make_svc(flow_list=None, param_list=None, debug_mode: bool = False) -> FlowSvc:
    """构造带内存存储桩的 FlowSvc, 并预置 ast_curr_info/ast_globals_dict"""
    svc = FlowSvc(conf=make_conf(debug_mode))
    svc.storage = FakeStorage(flow_list, param_list)
    svc.add_project_info(PROJECT_ID, "", "", "测试机器人", {}, 0, {})
    svc.ast_curr_info = {
        "__project_id__": PROJECT_ID,
        "__mode__": "",
        "__version__": "",
        "__process_id__": PROCESS_ID,
        "__process_name__": "主流程",
    }
    return svc


def gen(flow_list, param_list=None, debug_mode: bool = False):
    """把流程 JSON 走完整生成链路(词法→语法→AST 展开), 返回 (svc, 代码文本, map文本)"""
    svc = make_svc(flow_list, param_list, debug_mode)
    flow = Flow(svc=svc)
    code, map_res = flow._flow_display(PROJECT_ID, "", "", PROCESS_ID, "主流程")
    return svc, code, map_res


def atom(key: str, src: str = "", inputs=None, outputs=None, **extra) -> dict:
    """构造普通原子节点"""
    node = {
        "key": key,
        "src": src or "astronverse.fake.atomic.run",
        "inputList": inputs or [],
        "outputList": outputs or [],
    }
    node.update(extra)
    return node


def inp(key: str, value, ptype: str = "str", name: str = "", title: str = "") -> dict:
    """构造单段 inputList 项"""
    return {
        "key": key,
        "name": name or key,
        "title": title or key,
        "value": [{"type": ptype, "value": value}],
    }


def out(key: str, var: str) -> dict:
    """构造单段 outputList 项"""
    return {"key": key, "name": key, "title": key, "value": [{"type": "var", "value": var}]}


def ctrl(key: str, inputs=None, outputs=None) -> dict:
    """构造控制流节点(If/While/For/Try 等)"""
    return {"key": key, "inputList": inputs or [], "outputList": outputs or []}
