"""M5 视频×11 冒烟测试：imageio-ffmpeg 现场造 testsrc2 短视频（含/无音频、多分辨率），全链路真实执行。"""

import inspect
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/components/astronverse-video/src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/shared/astronverse-actionlib/src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/shared/astronverse-baseline/src"))

import random

from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image

from astronverse.video import AudioFormatType, WatermarkPositionType
from astronverse.video.error import BaseException
from astronverse.video.video import Video, _probe

FF = get_ffmpeg_exe()
TMP = tempfile.mkdtemp(prefix="m5_smoke_")
PASS, FAIL = [], []


def call(fn, *args, **kw):
    params = list(inspect.signature(fn).parameters)
    kw.update(dict(zip(params, args)))
    return fn(**kw)


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} | {name} {detail}")


def expect_raise(name, fn, *args, **kw):
    try:
        call(fn, *args, **kw)
        check(name, False, "未抛异常")
    except BaseException as e:
        ok = "astronverse" in type(e).__module__ or type(e).__name__ == "BaseException"
        check(name, ok, f"→ {str(e)[:70]}")
    except Exception as e:  # noqa: BLE001
        check(name, False, f"非预期异常 {type(e).__name__}: {e}")


def mkvideo(path, size, dur, audio=True, seed=0):
    """testsrc2 随机参数短视频（每支不同 pattern 保证画面非纯色）。"""
    cmd = [
        FF,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:duration={dur}:rate=15",
    ]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={440 + seed * 60}:duration={dur}"]
        cmd += ["-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", path]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return path


V1 = mkvideo(os.path.join(TMP, "v1.mp4"), "320x240", 5, audio=True, seed=1)
V2 = mkvideo(os.path.join(TMP, "v2.mp4"), "320x240", 3, audio=True, seed=2)
V3 = mkvideo(os.path.join(TMP, "v3.mp4"), "640x480", 3, audio=True, seed=3)  # 不同分辨率
VNA = mkvideo(os.path.join(TMP, "vna.mp4"), "320x240", 4, audio=False, seed=4)  # 无音频
WM = os.path.join(TMP, "wm.png")
random.seed(5)
_img = Image.new("RGB", (160, 60))
_img.putdata([(random.randrange(256), random.randrange(256), random.randrange(256)) for _ in range(160 * 60)])
_img.save(WM)
TXT = os.path.join(TMP, "fake.txt")
open(TXT, "w").write("not a video")

# ---------- 1. 校验/时长 ----------
check("check_video_valid 有效", call(Video.check_video_valid, V1) is True)
check("check_video_valid 不存在=False", call(Video.check_video_valid, "/tmp/none.mp4") is False)
check("check_video_valid 非视频=False", call(Video.check_video_valid, TXT) is False)
d = call(Video.get_video_duration, V1)
check("get_video_duration ≈5s", abs(d - 5) < 0.5, f"→ {d}")

# ---------- 2. 剪辑 ----------
cut = call(Video.cut_video, V1, 1, 2)
cd = _probe(cut)["duration"]
check("cut_video 1-3s ≈2s", abs(cd - 2) < 0.7, f"→ {cd}")
expect_raise("cut_video 起点超时长抛错", Video.cut_video, V1, 10, 1)
expect_raise("cut_video 时长<=0抛错", Video.cut_video, V1, 0, 0)

# ---------- 3. 音频 ----------
noaudio = call(Video.remove_audio, V1)
check("remove_audio 后无音频流", not _probe(noaudio)["has_audio"])
check("remove_audio 画面保留", abs(_probe(noaudio)["duration"] - 5) < 0.6)

mp3 = call(Video.extract_audio, V1, AudioFormatType.MP3)
check("extract_audio MP3", os.path.isfile(mp3) and os.path.getsize(mp3) > 1000 and mp3.endswith(".mp3"))
wav = call(Video.extract_audio, V1, AudioFormatType.WAV)
check("extract_audio WAV", os.path.isfile(wav) and os.path.getsize(wav) > 10000)
expect_raise("extract_audio 无音频流抛错", Video.extract_audio, VNA)

# ---------- 4. GIF/倍速 ----------
gif = call(Video.video_to_gif, V1, 0, 2, 10, 160)
g = Image.open(gif)
check("video_to_gif 多帧动图", getattr(g, "n_frames", 1) > 5 and g.size[0] == 160, f"帧数={getattr(g, 'n_frames', 1)}")

sp2 = call(Video.set_video_speed, V1, 2)
sd = _probe(sp2)["duration"]
check("set_video_speed 2x ≈2.5s", abs(sd - 2.5) < 0.6, f"→ {sd}")
sp05 = call(Video.set_video_speed, V1, 0.5)
check("set_video_speed 0.5x ≈10s", abs(_probe(sp05)["duration"] - 10) < 1.0, f"→ {_probe(sp05)['duration']}")
sp4 = call(Video.set_video_speed, V1, 4)
check(
    "set_video_speed 4x(音频atempo链) ≈1.25s", abs(_probe(sp4)["duration"] - 1.25) < 0.5, f"→ {_probe(sp4)['duration']}"
)
spna = call(Video.set_video_speed, VNA, 2)
check("set_video_speed 无音频视频", abs(_probe(spna)["duration"] - 2) < 0.5)
expect_raise("set_video_speed 超4倍抛错", Video.set_video_speed, V1, 8)

# ---------- 5. 批量前后置/合并 ----------
prep = call(Video.batch_prepend, [V2], V1)
check(
    "batch_prepend 3+5≈8s",
    len(prep) == 1 and abs(_probe(prep[0])["duration"] - 8) < 0.8,
    f"→ {_probe(prep[0])['duration']}",
)
app = call(Video.batch_append, f"{V1},{V2}", VNA)
check("batch_append 逗号串入参 5+4≈9s", len(app) == 2 and abs(_probe(app[0])["duration"] - 9) < 0.8)
merged = call(Video.concat_videos, [V1, V2])
check("concat_videos 5+3≈8s", abs(_probe(merged)["duration"] - 8) < 0.8, f"→ {_probe(merged)['duration']}")
expect_raise("concat 分辨率不一致抛错", Video.concat_videos, [V1, V3])
expect_raise("concat 单视频抛错", Video.concat_videos, [V1])
expect_raise("batch_prepend 空列表抛错", Video.batch_prepend, [], V1)

# ---------- 6. 水印 ----------
wmv = call(Video.add_video_watermark, V1, WM, WatermarkPositionType.BOTTOM_RIGHT, 50)
wi = _probe(wmv)
check("add_video_watermark 输出有效", os.path.isfile(wmv) and abs(wi["duration"] - 5) < 0.6 and wi["width"] == 320)
wmv2 = call(Video.add_video_watermark, VNA, WM, WatermarkPositionType.TOP_CENTER, 100)
check("add_video_watermark 无音频视频", abs(_probe(wmv2)["duration"] - 4) < 0.6)
expect_raise("watermark 不存在图片抛错", Video.add_video_watermark, V1, "/tmp/none.png")

print(f"\n===== M5 冒烟 {len(PASS)}/{len(PASS) + len(FAIL)} 通过 =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
