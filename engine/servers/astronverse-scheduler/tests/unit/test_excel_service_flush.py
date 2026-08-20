"""ExcelService flush 重入防护的并发单元测试。

背景: 读/写接口的 flush_pending 与防抖定时器回调 _flush_pending 可能并发,
修复前两者都在锁外应用更新, 同一批待更新可能被双取并发 apply(读-改-写交叉丢写)。
修复后通过 Condition + _flushing 标志串行化: 后到者等待进行中的 flush 完成。

运行: cd engine/servers/astronverse-scheduler && .venv/bin/python -m unittest tests.unit.test_excel_service_flush
"""

import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from astronverse.scheduler.core.datatable.excel_service import ExcelService


class TestFlushConcurrencyGuard(unittest.TestCase):
    def setUp(self):
        # 清理类级共享状态, 避免用例间串扰
        with ExcelService._pending_lock:
            ExcelService._pending_updates.clear()
            if ExcelService._flush_timer is not None:
                ExcelService._flush_timer.cancel()
                ExcelService._flush_timer = None
        ExcelService._flushing = False

    def tearDown(self):
        self.setUp()

    def test_concurrent_flush_applies_batch_exactly_once(self):
        """并发 flush_pending 与 _flush_pending: 同一批更新只被 apply 一次且不并发执行"""
        applied = []
        active = {"n": 0, "max": 0}
        lock = threading.Lock()

        def fake_apply(file_path, updates):
            with lock:
                active["n"] += 1
                active["max"] = max(active["max"], active["n"])
            try:
                applied.append((file_path, list(updates)))
            finally:
                with lock:
                    active["n"] -= 1

        ExcelService._pending_updates["/fake/t.xlsx"] = [{"row": 1, "col": 1, "value": "v"}]

        barrier = threading.Barrier(4)

        def worker(fn):
            barrier.wait()
            fn()

        threads = [
            threading.Thread(target=worker, args=(ExcelService.flush_pending,)),
            threading.Thread(target=worker, args=(ExcelService._flush_pending,)),
            threading.Thread(target=worker, args=(ExcelService.flush_pending,)),
            threading.Thread(target=worker, args=(ExcelService._flush_pending,)),
        ]
        with mock.patch.object(ExcelService, "_apply_updates", side_effect=fake_apply):
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
                self.assertFalse(t.is_alive(), "flush 线程未在 10s 内结束(疑似死锁)")

        self.assertEqual(len(applied), 1, f"同一批更新应只被 apply 一次, 实际 {len(applied)} 次")
        self.assertEqual(active["max"], 1, "apply 不允许并发执行")
        self.assertFalse(ExcelService._flushing, "_flushing 标志应复位")

    def test_second_flush_waits_and_sees_later_updates(self):
        """第一个 flush 进行中时新入队的更新, 由等待后的第二个 flush 落盘(不丢写)"""
        applied = []
        release = threading.Event()

        def slow_apply(file_path, updates):
            release.wait(timeout=10)
            applied.extend(updates)

        with mock.patch.object(ExcelService, "_apply_updates", side_effect=slow_apply):
            ExcelService._pending_updates["/fake/a.xlsx"] = [{"value": "first"}]
            t1 = threading.Thread(target=ExcelService.flush_pending)
            t1.start()

            # t1 持有 _flushing 期间入队第二批并 flush: 必须等待 t1 完成后才处理
            for _ in range(50):
                if ExcelService._flushing:
                    break
            else:
                release.set()
                t1.join(timeout=10)
                self.fail("首个 flush 未进入 flushing 状态")

            ExcelService._pending_updates["/fake/b.xlsx"] = [{"value": "second"}]
            t2 = threading.Thread(target=ExcelService.flush_pending)  # 应等待 t1 结束后再取第二批
            t2.start()
            release.set()
            t1.join(timeout=10)
            t2.join(timeout=10)
            self.assertFalse(t2.is_alive(), "第二个 flush 线程未在 10s 内结束(疑似死锁)")

        self.assertEqual([u["value"] for u in applied], ["first", "second"])
        self.assertFalse(ExcelService._flushing)
        self.assertEqual(ExcelService._pending_updates, {})


if __name__ == "__main__":
    unittest.main()
