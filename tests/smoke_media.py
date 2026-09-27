"""Offline integration: serve generated media locally, download, remux and extract MP3."""
import contextlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deno
import imageio_ffmpeg
import yt_dlp
from engine import build_options


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        source = folder / "sample.mp4"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=blue:s=320x180:r=10", "-f", "lavfi", "-i", "sine=frequency=440",
                        "-t", "1", "-c:v", "libx264", "-c:a", "aac", str(source)], check=True,
                       capture_output=True)
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=temp))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            for mode, extension in [("video", ".mkv"), ("audio", ".mp3")]:
                files = []
                options = build_options({"mode": mode, "quality": "最佳畫質", "folder": str(folder / mode)}, ffmpeg, deno.find_deno_bin())
                options["post_hooks"] = [files.append]
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.download([f"http://127.0.0.1:{server.server_port}/sample.mp4"])
                assert len(files) == 1, files
                output = Path(files[0])
                assert output.suffix == extension and output.stat().st_size > 1000, files
                subprocess.run([ffmpeg, "-v", "error", "-i", str(output), "-f", "null", "-"],
                               check=True, capture_output=True)
                print(f"PASS {mode}: {output.name}, {output.stat().st_size} bytes, decodes successfully")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
