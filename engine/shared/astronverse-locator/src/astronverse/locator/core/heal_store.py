"""自愈缓存与拾取指标(E2 持久化 + 可观测性)。

- 自愈缓存: 自愈成功后的放宽路径持久化到本地, 下次定位先试缓存的"已修复版",
  避免每次运行重复昂贵的自愈探索; 缓存失效(UI 再次变化)时自动移除。
- 拾取指标: 进程内计数定位次数/自愈命中/CV 降级命中等, 支持 WS 查询辅助调优。
"""

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from astronverse.baseline.logger.logger import logger

# 缓存条目上限, 超出按最旧淘汰
HEAL_CACHE_MAX_ENTRIES = 500

_lock = threading.Lock()

_metrics = {
    "locate_total": 0,
    "locate_success": 0,
    "locate_fail": 0,
    "heal_attempt": 0,
    "heal_success": 0,
    "heal_cache_hit": 0,
    "heal_cache_invalidated": 0,
    "cv_fallback_attempt": 0,
    "cv_fallback_success": 0,
    "last_locate_ms": 0,
}


def _cache_path() -> Path:
    return Path(os.environ.get("ASTRON_HEAL_CACHE") or (Path.home() / ".astronverse" / "heal_cache.json"))


# ---------------- 指标 ----------------


def record_metric(event: str) -> None:
    """计数类指标 +1(未知事件忽略)"""
    with _lock:
        if event in _metrics:
            _metrics[event] += 1


def record_timing(ms: float) -> None:
    """记录最近一次定位耗时"""
    with _lock:
        _metrics["last_locate_ms"] = round(ms, 1)


def metrics_snapshot() -> dict:
    with _lock:
        return dict(_metrics)


def reset_metrics() -> None:
    """测试用: 清零全部指标"""
    with _lock:
        for key in _metrics:
            _metrics[key] = 0


def format_report_tips(report) -> list:
    """把 locator 定位时回写的自愈/CV 降级信息转为用户可读提示(供步骤日志展示)。

    report 由调用方传入 LocatorManager.locator(report=...), 命中自愈缓存/自愈成功/
    CV 降级成功或歧义时被回写; 无命中时返回空列表(不产生日志噪音)。
    """
    if not isinstance(report, dict):
        return []
    tips = []
    if report.get("heal_cache"):
        tips.append("命中自愈缓存: 直接复用此前自动修复的元素路径")
    if report.get("healed"):
        # repair_hint 为自愈引擎生成的具体修复描述(放宽了哪些匹配条件)
        tips.append(report.get("repair_hint") or "元素定位失败, 已自动修复")
    if report.get("cv_fallback"):
        tips.append("元素定位失败, 已降级为图像匹配并成功")
    if report.get("cv_ambiguous"):
        tips.append(f"屏幕存在 {report['cv_ambiguous']} 处图像相似命中, 图像降级已中止, 建议重新拾取该元素")
    return tips


# ---------------- 自愈缓存 ----------------


def element_cache_key(element: dict) -> str:
    """基于 app+原始 path 的稳定键, 同一元素共享一条缓存"""
    identity = {"app": element.get("app"), "path": element.get("path")}
    raw = json.dumps(identity, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    path = _cache_path()
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"自愈缓存读取失败, 按空缓存处理: {e}")
    return {}


def _save_cache(cache: dict) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 审计修复(M1): 缓存由 executor/picker 两进程共写, 先写临时文件再原子替换,
        # 避免并发下撕裂写导致整份缓存 json.loads 失败而丢失全部自愈历史
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as e:
        logger.warning(f"自愈缓存写入失败(不影响定位): {e}")


def heal_cache_get(element: dict):
    """命中返回修复后的 path(list), 否则 None"""
    key = element_cache_key(element)
    with _lock:
        entry = _load_cache().get(key)
    return entry.get("path") if entry else None


def heal_cache_put(element: dict, healed_path: list, relaxations: list) -> None:
    """自愈成功后写入缓存(超上限淘汰最旧条目)"""
    key = element_cache_key(element)
    with _lock:
        cache = _load_cache()
        if len(cache) >= HEAL_CACHE_MAX_ENTRIES and key not in cache:
            oldest = min(cache.items(), key=lambda kv: kv[1].get("ts", 0))[0]
            cache.pop(oldest, None)
        cache[key] = {
            "path": healed_path,
            "relaxations": relaxations,
            "app": element.get("app"),
            "ts": time.time(),
        }
        _save_cache(cache)
    logger.info(f"自愈结果已缓存(共 {len(relaxations)} 级放宽), 下次定位将优先使用修复版路径")


def heal_cache_drop(element: dict) -> None:
    """缓存的修复路径再次失效时移除, 回退正常自愈探索"""
    key = element_cache_key(element)
    with _lock:
        cache = _load_cache()
        if key in cache:
            cache.pop(key)
            _save_cache(cache)


def heal_cache_drop_key(key: str) -> bool:
    """按缓存键删除单条(供指标面板手动清理), 返回是否实际删除"""
    with _lock:
        cache = _load_cache()
        if key in cache:
            cache.pop(key)
            _save_cache(cache)
            return True
    return False


def heal_cache_all() -> dict:
    """全部缓存条目(供报告/排查)"""
    with _lock:
        return _load_cache()
