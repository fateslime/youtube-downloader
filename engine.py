"""Download worker. JSON lines on stdout keep the GUI responsive and isolated."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
QUALITIES = {"最佳畫質": None, "最高 2160p / 4K": 2160, "最高 1440p": 1440,
             "最高 1080p": 1080, "最高 720p": 720, "最高 480p": 480}


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("請先貼上 YouTube 影片網址。")
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
        raise ValueError("請使用一般的 YouTube 影片網址。")
    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}:
                video_id = parts[1]
    if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("請輸入有效的 YouTube 單支影片網址（支援 Shorts）。")
    return f"https://www.youtube.com/watch?v={video_id}"


def emit(kind: str, **data) -> None:
    print(json.dumps({"type": kind, **data}, ensure_ascii=False), flush=True)


class Logger:
    def debug(self, message):
        if not message.startswith("[debug]"):
            emit("log", text=message)

    def warning(self, message):
        emit("log", text="提醒：" + message)

    def error(self, message):
        emit("log", text=message)


def build_options(config: dict, ffmpeg: str, deno: str) -> dict:
    mode = config.get("mode", "video")
    quality = config.get("quality", "最高 1080p")
    if mode not in {"video", "audio"} or quality not in QUALITIES:
        raise ValueError("不支援的格式或畫質設定。")
    options = {
        "noplaylist": True, "quiet": True, "no_warnings": False,
        "logger": Logger(), "nocolor": True, "cachedir": str(ROOT / ".cache" / "yt-dlp"),
        "socket_timeout": 20, "retries": 3, "fragment_retries": 3,
        "continuedl": True, "overwrites": False, "windowsfilenames": True,
        "ffmpeg_location": ffmpeg, "js_runtimes": {"deno": {"path": deno}},
        "outtmpl": str(Path(config.get("folder", ROOT / "downloads")) /
                       "%(title).150B [%(id)s].%(ext)s"),
    }
    if mode == "audio":
        options.update(format="bestaudio/best", postprocessors=[{
            "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192",
        }])
    else:
        height = QUALITIES[quality]
        cap = f"[height<={height}]" if height else ""
        options.update(format=f"bv*{cap}+ba/b{cap}", merge_output_format="mkv",
                       postprocessors=[{"key": "FFmpegVideoRemuxer", "preferedformat": "mkv"}])
    return options


def friendly_error(error: Exception) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(error))
    lower = text.lower()
    if "sign in" in lower or "bot" in lower:
        return "YouTube 要求登入或額外驗證，這支影片暫時無法下載。可稍後重試或改用其他公開影片。\n\n" + text
    if "private" in lower or "unavailable" in lower:
        return "影片無法存取，可能已移除、設為私人或有地區限制。\n\n" + text
    if "requested format" in lower:
        return "這支影片沒有符合設定的格式，請改選「最佳畫質」再試一次。\n\n" + text
    if "permission" in lower or "denied" in lower:
        return "無法存取檔案或網路，請確認儲存位置可寫入、檔案未被占用。\n\n" + text
    return text


def run_worker(config: dict) -> int:
    try:
        import deno
        import imageio_ffmpeg
        import yt_dlp

        url = normalize_url(config["url"])
        options = build_options(config, imageio_ffmpeg.get_ffmpeg_exe(), deno.find_deno_bin())
        last_update = 0.0
        files: list[str] = []

        def progress(data):
            nonlocal last_update
            status = data.get("status")
            if status == "downloading":
                now = time.monotonic()
                if now - last_update < 0.15:
                    return
                last_update = now
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes") or 0
                emit("progress", percent=min(100, downloaded * 100 / total) if total else None,
                     downloaded=downloaded, total=total, speed=data.get("speed"), eta=data.get("eta"),
                     filename=Path(data.get("filename", "")).name)
            elif status == "finished":
                emit("status", text="串流下載完成，正在處理音訊／影片…")

        def postprocess(data):
            if data.get("status") == "started":
                emit("status", text="正在合併影片或轉換音訊，請稍候…")

        def finished(path):
            files.append(str(Path(path).resolve()))

        options.update(progress_hooks=[progress], postprocessor_hooks=[postprocess],
                       post_hooks=[finished])
        with yt_dlp.YoutubeDL(options) as ydl:
            emit("status", text="正在讀取 YouTube 影片資訊…")
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError("找不到影片資訊。")
            if info.get("is_live") or info.get("live_status") == "is_upcoming":
                raise ValueError("目前只支援已發布的影片，請等待直播或首播結束後再下載。")
            emit("info", title=info.get("title", "未命名影片"),
                 channel=info.get("uploader", "未知頻道"), duration=info.get("duration"))
            if config.get("action") == "inspect":
                emit("done", files=[], action="inspect")
                return 0
            folder = Path(config["folder"]).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
            # Test write access before downloading a potentially large file.
            import tempfile
            with tempfile.TemporaryFile(dir=folder):
                pass
            emit("status", text="準備下載…")
            ydl.process_ie_result(info, download=True)
            if not files or not all(Path(path).is_file() for path in files):
                raise RuntimeError("下載程序結束，但沒有找到完成的輸出檔案。請查看詳細記錄。")
            emit("done", files=files, action="download")
        return 0
    except Exception as error:
        emit("error", text=friendly_error(error))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    sys.exit(run_worker(json.loads(sys.stdin.readline())))
