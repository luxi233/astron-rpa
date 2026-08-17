"""视频处理原子能力：校验/时长/剪辑/音频/转GIF/倍速/批量前后拼接/合并/水印（imageio-ffmpeg，跨平台免安装）。"""

import os
import re
import subprocess

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.video import AudioFormatType, WatermarkPositionType
from astronverse.video.error import (
    FFMPEG_NOT_FOUND_ERROR_FORMAT,
    FILE_NOT_FOUND_ERROR_FORMAT,
    INVALID_PARAMS_ERROR_FORMAT,
    INVALID_VIDEO_ERROR_FORMAT,
    VIDEO_PROCESS_ERROR_FORMAT,
    BaseException,
)


def _ffmpeg() -> str:
    """返回 imageio-ffmpeg 自带的 ffmpeg 可执行文件路径。"""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception as e:
        raise BaseException(FFMPEG_NOT_FOUND_ERROR_FORMAT.format(str(e)), "ffmpeg不可用，请检查 imageio-ffmpeg 安装")


def _check_file(path: str):
    if not path or not os.path.isfile(path):
        raise BaseException(FILE_NOT_FOUND_ERROR_FORMAT.format(str(path)), "文件不存在")


def _run(cmd: list) -> str:
    """执行 ffmpeg 命令，非 0 退出码抛业务异常。"""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-500:].replace("\n", " ").strip()
        raise BaseException(VIDEO_PROCESS_ERROR_FORMAT.format(tail), "ffmpeg执行失败，详见错误信息")
    return proc.stderr or ""


def _probe(path: str) -> dict:
    """解析 ffmpeg -i 的 stderr，返回 {duration, width, height, has_audio}。"""
    _check_file(path)
    proc = subprocess.run([_ffmpeg(), "-i", path], capture_output=True, text=True, timeout=120)
    err = proc.stderr or ""
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if not m:
        raise BaseException(INVALID_VIDEO_ERROR_FORMAT.format(str(path)), "无法解析视频时长，文件可能损坏")
    duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r"Stream.*Video:.*?(\d{2,5})x(\d{2,5})", err)
    width, height = (int(v.group(1)), int(v.group(2))) if v else (0, 0)
    return {
        "duration": round(duration, 3),
        "width": width,
        "height": height,
        "has_audio": "Audio:" in err,
    }


def _parse_files(files) -> list:
    """文件入参统一：list/tuple 或逗号分隔字符串。"""
    if isinstance(files, str):
        return [p.strip() for p in files.split(",") if p.strip()]
    if isinstance(files, (list, tuple)):
        return [str(p).strip() for p in files if str(p).strip()]
    return []


def _out_path(src: str, suffix: str, save_path: str = "", ext: str = "") -> str:
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        return save_path
    d = os.path.dirname(os.path.abspath(src))
    name = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(d, f"{name}_{suffix}{ext or os.path.splitext(src)[1]}")


_REENCODE = ["-pix_fmt", "yuv420p", "-movflags", "+faststart"]


def _concat_pair(inputs: list, out_path: str):
    """拼接多个同分辨率视频（filter concat 再编码）。"""
    cmd = [_ffmpeg()]
    for f in inputs:
        cmd += ["-i", f]
    has_audio = all(_probe(f)["has_audio"] for f in inputs)
    n = len(inputs)
    if has_audio:
        fc = "".join(f"[{i}:v][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-c:a", "aac"]
    else:
        fc = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
        cmd += ["-filter_complex", fc, "-map", "[v]", "-c:v", "libx264"]
    cmd += _REENCODE + [out_path]
    _run(cmd)


def _atempo_chain(speed: float) -> str:
    """atempo 单级范围 0.5-2.0，超范围拆链。"""
    parts = []
    s = speed
    while s > 2.0 + 1e-9:
        parts.append("2.0")
        s /= 2.0
    while s < 0.5 - 1e-9:
        parts.append("0.5")
        s /= 0.5
    parts.append(f"{s:.4f}")
    return ",".join(f"atempo={p}" for p in parts)


_POSITION_EXPR = {
    "top_left": "10:10",
    "top_center": "(main_w-overlay_w)/2:10",
    "top_right": "main_w-overlay_w-10:10",
    "middle_left": "10:(main_h-overlay_h)/2",
    "middle_center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
    "middle_right": "main_w-overlay_w-10:(main_h-overlay_h)/2",
    "bottom_left": "10:main_h-overlay_h-10",
    "bottom_center": "(main_w-overlay_w)/2:main_h-overlay_h-10",
    "bottom_right": "main_w-overlay_w-10:main_h-overlay_h-10",
}


class Video:
    """视频处理原子能力集合（imageio-ffmpeg，免系统安装）。"""

    # ---------- 基础信息 ----------
    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[atomicMg.param("file_path", types="Str")],
        outputList=[atomicMg.param("is_valid", types="Bool")],
    )
    def check_video_valid(file_path: str = ""):
        """校验视频文件是否有效可解析（不抛错，无效返回False）"""
        if not file_path or not os.path.isfile(file_path):
            return False
        try:
            _probe(file_path)
            return True
        except BaseException:
            return False

    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[atomicMg.param("file_path", types="Str")],
        outputList=[atomicMg.param("duration", types="Float")],
    )
    def get_video_duration(file_path: str = ""):
        """获取视频时长（秒）"""
        return _probe(file_path)["duration"]

    # ---------- 剪辑/音频 ----------
    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("start", types="Float"),
            atomicMg.param("duration", types="Float"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("video_path_out", types="Str")],
    )
    def cut_video(file_path: str = "", start: float = 0, duration: float = 0, save_path: str = ""):
        """剪辑视频片段（从第start秒起duration秒，流复制快速模式），输出新文件路径"""
        _check_file(file_path)
        start = max(0.0, float(start or 0))
        duration = float(duration or 0)
        if duration <= 0:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(f"duration={duration}"), "剪辑时长须大于0")
        total = _probe(file_path)["duration"]
        if start >= total:
            raise BaseException(
                INVALID_PARAMS_ERROR_FORMAT.format(f"start={start}"), f"起始秒数超出视频时长({total:.2f}s)"
            )
        out = _out_path(file_path, "cut", save_path)
        cmd = [_ffmpeg(), "-y", "-ss", f"{start:.3f}", "-i", file_path, "-t", f"{duration:.3f}", "-c", "copy", out]
        _run(cmd)
        return out

    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("video_path_out", types="Str")],
    )
    def remove_audio(file_path: str = "", save_path: str = ""):
        """去除视频中的音频（保留画面），输出新文件路径"""
        _check_file(file_path)
        out = _out_path(file_path, "noaudio", save_path)
        _run([_ffmpeg(), "-y", "-i", file_path, "-c", "copy", "-an", out])
        return out

    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("audio_format", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("audio_path_out", types="Str")],
    )
    def extract_audio(file_path: str = "", audio_format: AudioFormatType = AudioFormatType.MP3, save_path: str = ""):
        """从视频中提取音频（MP3/WAV/AAC），输出音频文件路径"""
        fmt = audio_format.value if isinstance(audio_format, AudioFormatType) else str(audio_format or "mp3")
        codec = {"mp3": "libmp3lame", "wav": "pcm_s16le", "aac": "aac"}.get(fmt)
        if not codec:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(fmt), "音频格式仅支持 mp3/wav/aac")
        info = _probe(file_path)
        if not info["has_audio"]:
            raise BaseException(VIDEO_PROCESS_ERROR_FORMAT.format(str(file_path)), "视频中无音频流")
        out = _out_path(file_path, "audio", save_path, ext=f".{fmt}")
        _run([_ffmpeg(), "-y", "-i", file_path, "-vn", "-acodec", codec, out])
        return out

    # ---------- GIF/倍速 ----------
    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("start", types="Float", required=False),
            atomicMg.param("duration", types="Float", required=False),
            atomicMg.param("fps", types="Int", required=False),
            atomicMg.param("width", types="Int", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("gif_path_out", types="Str")],
    )
    def video_to_gif(
        file_path: str = "",
        start: float = 0,
        duration: float = 0,
        fps: int = 10,
        width: int = 480,
        save_path: str = "",
    ):
        """将视频片段转为GIF动图（可设起始/时长/帧率/宽度），输出GIF文件路径"""
        _check_file(file_path)
        start = max(0.0, float(start or 0))
        duration = float(duration or 0)
        fps = min(30, max(1, int(fps or 10)))
        width = min(4096, max(16, int(width or 480)))
        out = _out_path(file_path, "gif", save_path, ext=".gif")
        vf = f"fps={fps},scale={width}:-2:flags=lanczos"
        cmd = [_ffmpeg(), "-y", "-ss", f"{start:.3f}"]
        if duration > 0:
            cmd += ["-t", f"{duration:.3f}"]
        cmd += ["-i", file_path, "-vf", vf, "-loop", "0", out]
        _run(cmd)
        return out

    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("speed", types="Float"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("video_path_out", types="Str")],
    )
    def set_video_speed(file_path: str = "", speed: float = 1.0, save_path: str = ""):
        """调整视频播放速度（0.25-4倍，音画同步变速），输出新文件路径"""
        _check_file(file_path)
        speed = float(speed or 1.0)
        if not (0.25 <= speed <= 4.0):
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(f"speed={speed}"), "倍速须在0.25-4之间")
        out = _out_path(file_path, "speed", save_path)
        info = _probe(file_path)
        if info["has_audio"]:
            fc = f"[0:v]setpts=PTS/{speed:.4f}[v];[0:a]{_atempo_chain(speed)}[a]"
            cmd = [
                _ffmpeg(),
                "-y",
                "-i",
                file_path,
                "-filter_complex",
                fc,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
            ]
        else:
            cmd = [
                _ffmpeg(),
                "-y",
                "-i",
                file_path,
                "-vf",
                f"setpts=PTS/{speed:.4f}",
                "-an",
                "-c:v",
                "libx264",
            ]
        _run(cmd + _REENCODE + [out])
        return out

    # ---------- 拼接/合并 ----------
    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("video_files", types="List"),
            atomicMg.param("prepend_file", types="Str"),
            atomicMg.param(
                "save_dir",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "folder"}
                ),
            ),
        ],
        outputList=[atomicMg.param("video_paths_out", types="List")],
    )
    def batch_prepend(video_files="", prepend_file: str = "", save_dir: str = ""):
        """批量前置视频（将prepend视频拼到每个视频开头），输出文件路径列表"""
        files = _parse_files(video_files)
        if not files:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(str(video_files)), "视频列表不能为空")
        _check_file(prepend_file)
        outs = []
        for f in files:
            _check_file(f)
            out = _out_path(
                f,
                "prepended",
                os.path.join(save_dir, f"{os.path.splitext(os.path.basename(f))[0]}_prepended.mp4") if save_dir else "",
            )
            _concat_pair([prepend_file, f], out)
            outs.append(out)
        return outs

    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("video_files", types="List"),
            atomicMg.param("append_file", types="Str"),
            atomicMg.param(
                "save_dir",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "folder"}
                ),
            ),
        ],
        outputList=[atomicMg.param("video_paths_out", types="List")],
    )
    def batch_append(video_files="", append_file: str = "", save_dir: str = ""):
        """批量后置视频（将append视频拼到每个视频结尾），输出文件路径列表"""
        files = _parse_files(video_files)
        if not files:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(str(video_files)), "视频列表不能为空")
        _check_file(append_file)
        outs = []
        for f in files:
            _check_file(f)
            out = _out_path(
                f,
                "appended",
                os.path.join(save_dir, f"{os.path.splitext(os.path.basename(f))[0]}_appended.mp4") if save_dir else "",
            )
            _concat_pair([f, append_file], out)
            outs.append(out)
        return outs

    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("video_files", types="List"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("video_path_out", types="Str")],
    )
    def concat_videos(video_files="", save_path: str = ""):
        """合并多个视频为一个（自动校验分辨率一致，不一致报错），输出新文件路径"""
        files = _parse_files(video_files)
        if len(files) < 2:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(str(video_files)), "合并至少需要2个视频")
        infos = []
        for f in files:
            _check_file(f)
            infos.append(_probe(f))
        sizes = {(i["width"], i["height"]) for i in infos}
        if len(sizes) > 1:
            detail = ", ".join(f"{f}={i['width']}x{i['height']}" for f, i in zip(files, infos))
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(detail), "视频分辨率不一致，无法合并")
        first = files[0]
        out = _out_path(first, "merged", save_path or os.path.join(os.path.dirname(first), "videos_merged.mp4"))
        _concat_pair(files, out)
        return out

    # ---------- 水印 ----------
    @staticmethod
    @atomicMg.atomic(
        "Video",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("watermark_path", types="Str"),
            atomicMg.param("position", required=False),
            atomicMg.param("opacity", types="Int", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("video_path_out", types="Str")],
    )
    def add_video_watermark(
        file_path: str = "",
        watermark_path: str = "",
        position: WatermarkPositionType = WatermarkPositionType.BOTTOM_RIGHT,
        opacity: int = 100,
        save_path: str = "",
    ):
        """为视频添加图片水印（九宫格位置+透明度，随画面全程显示），输出新文件路径"""
        from PIL import Image

        _check_file(file_path)
        _check_file(watermark_path)
        pos = position.value if isinstance(position, WatermarkPositionType) else str(position or "bottom_right")
        expr = _POSITION_EXPR.get(pos)
        if not expr:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT.format(pos), "不支持的水印位置")
        opacity = min(100, max(1, int(opacity or 100)))
        out = _out_path(file_path, "watermarked", save_path)
        # 预处理水印：RGBA + 整体透明度（Pillow 一次 putalpha，无 paste 二次衰减）
        try:
            wm = Image.open(watermark_path).convert("RGBA")
            if opacity < 100:
                alpha = wm.getchannel("A").point(lambda a: a * opacity // 100)
                wm.putalpha(alpha)
            wm_tmp = os.path.join(os.path.dirname(os.path.abspath(out)), f"_wm_{os.getpid()}.png")
            wm.save(wm_tmp, "PNG")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(VIDEO_PROCESS_ERROR_FORMAT.format(str(e)), "水印图片处理失败")
        try:
            fc = f"[1:v]format=rgba[wm];[0:v][wm]overlay={expr}[v]"
            info = _probe(file_path)
            has_audio = info["has_audio"]
            cmd = [_ffmpeg(), "-y", "-i", file_path, "-i", wm_tmp, "-filter_complex", fc, "-map", "[v]"]
            if has_audio:
                cmd += ["-map", "0:a?", "-c:a", "aac"]
            cmd += ["-c:v", "libx264"] + _REENCODE + [out]
            _run(cmd)
            return out
        finally:
            if os.path.isfile(wm_tmp):
                os.remove(wm_tmp)
