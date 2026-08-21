"""J4 录制收尾超时上限单测。

close 等待转码完成(exec_res 轮询): 正常完成立即返回; ffmpeg 挂死时按
RECORDING_CLOSE_WAIT_TIMEOUT 超时后放弃等待继续退出, 不再死等。
"""

import threading
import time

import astronverse.executor.debug.recording as recording_mod
from astronverse.executor.debug.recording import RecordingTool


class _FakeSvc:
    pass


def _tool(tmp_path, open_rec=True):
    t = RecordingTool(_FakeSvc())
    t.init("proj1", "exec1", config={"open": open_rec, "file_path": str(tmp_path), "file_clear_time": 0})
    t.start_time = int(time.time()) - 10  # 跳过 close 内"不足3s"的补等
    return t


def test_未开启录制时close无等待(tmp_path):
    t = _tool(tmp_path, open_rec=False)
    t.start()  # exec_res 置 True
    begin = time.time()
    t.close(True)
    assert time.time() - begin < 0.5


def test_exec_res正常回写时立即返回(tmp_path, monkeypatch):
    t = _tool(tmp_path)

    def _fake_res():
        time.sleep(0.1)
        t.exec_res = True

    threading.Thread(target=_fake_res, daemon=True).start()
    begin = time.time()
    t.close(True)
    assert time.time() - begin < 1.0
    assert t.exec_res is None  # 等待完成后复位


def test_转码挂死时超时后继续退出(tmp_path, monkeypatch):
    monkeypatch.setattr(recording_mod, "RECORDING_CLOSE_WAIT_TIMEOUT", 0.3)
    t = _tool(tmp_path)
    begin = time.time()
    t.close(False)  # exec_res 永不回写 → 走超时分支
    elapsed = time.time() - begin
    assert elapsed >= 0.3  # 确实等到了上限
    assert elapsed < 2.0  # 而非无限等待
    assert t.exec_res is None
