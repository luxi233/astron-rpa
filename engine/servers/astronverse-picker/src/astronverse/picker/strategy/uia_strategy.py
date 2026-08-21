from astronverse.picker import IElement
from astronverse.picker.engines.uia_picker import UIAElement, UIAPicker, uia_picker
from astronverse.picker.strategy.types import StrategySvc


def uia_default_strategy(strategy_svc: StrategySvc) -> IElement:
    """
    默认策略
    strategy_svc 策略上下文
    """

    # 深度捕获模式(对应影刀"深度模式"): 标准模式选不中/选中范围过大时,
    # 以更大遍历深度下钻 UIA 树, 探测更深的隐藏层级
    kwargs = {
        # 下面就是配置
        # 启用控件缓存(带窗口句柄+进程id+TTL失效策略), 避免鼠标移动时逐帧全子树重遍历
        "used_cache": True,
        "root_need_init": True,
        "ignore_parent_zero": True,
    }
    if strategy_svc.data and strategy_svc.data.get("deep"):
        kwargs["max_depth"] = UIAPicker.MAX_SEARCH_DEPTH * 2

    ele = uia_picker.get_element(
        root=UIAElement(control=strategy_svc.start_control),
        point=strategy_svc.last_point,
        **kwargs,
    )
    return ele
