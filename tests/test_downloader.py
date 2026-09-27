import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import engine
from app import duration, size


class UrlTests(unittest.TestCase):
    def test_supported_urls_are_canonical_and_playlist_removed(self):
        for url in ["https://www.youtube.com/watch?v=BaW_jenozKc&list=PLexample",
                    "youtu.be/BaW_jenozKc?t=10", "https://m.youtube.com/watch?v=BaW_jenozKc",
                    "https://youtube.com/shorts/BaW_jenozKc", "https://youtube.com/live/BaW_jenozKc"]:
            with self.subTest(url=url):
                self.assertEqual(engine.normalize_url(url), "https://www.youtube.com/watch?v=BaW_jenozKc")

    def test_rejects_non_video_or_misleading_urls(self):
        for url in ["", "https://youtube.com.evil.test/watch?v=BaW_jenozKc",
                    "https://youtube.com/playlist?list=abc", "https://youtu.be/short",
                    "https://user:pass@youtube.com/watch?v=BaW_jenozKc",
                    "file:///etc/passwd", "https://example.com/watch?v=BaW_jenozKc"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                engine.normalize_url(url)


class OptionTests(unittest.TestCase):
    def test_video_caps_both_separate_and_combined_streams(self):
        options = engine.build_options({"quality": "最高 720p", "folder": "downloads"}, "ffmpeg", "deno")
        self.assertEqual(options["format"], "bv*[height<=720]+ba/b[height<=720]")
        self.assertEqual(options["merge_output_format"], "mkv")
        self.assertFalse(options["overwrites"])

    def test_best_quality_has_no_cap(self):
        options = engine.build_options({"quality": "最佳畫質"}, "ffmpeg", "deno")
        self.assertEqual(options["format"], "bv*+ba/b")

    def test_mp3_has_no_video_quality_filter(self):
        options = engine.build_options({"mode": "audio"}, "ffmpeg", "deno")
        self.assertEqual(options["format"], "bestaudio/best")
        self.assertEqual(options["postprocessors"][0]["preferredcodec"], "mp3")

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            engine.build_options({"mode": "oops"}, "ffmpeg", "deno")


class WorkerTests(unittest.TestCase):
    def run_fake(self, action="download", live=False, make_file=True):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "測試 [BaW_jenozKc].mkv"
            options = {}

            class FakeYDL:
                def __init__(self, opts):
                    options.update(opts)

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

                def extract_info(self, url, download):
                    return {"title": "測試影片", "uploader": "測試頻道", "duration": 10, "is_live": live}

                def process_ie_result(self, info, download):
                    for hook in options["progress_hooks"]:
                        hook({"status": "downloading", "downloaded_bytes": 5, "total_bytes": 10})
                    if make_file:
                        output.write_bytes(b"test")
                        for hook in options["post_hooks"]:
                            hook(str(output))

            buffer = io.StringIO()
            with patch("yt_dlp.YoutubeDL", FakeYDL), contextlib.redirect_stdout(buffer):
                code = engine.run_worker({"url": "youtu.be/BaW_jenozKc", "folder": folder, "action": action})
            return code, [json.loads(line) for line in buffer.getvalue().splitlines()]

    def test_download_reports_verified_output(self):
        code, events = self.run_fake()
        self.assertEqual(code, 0)
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(len(events[-1]["files"]), 1)
        self.assertEqual(next(e["percent"] for e in events if e["type"] == "progress"), 50)

    def test_inspect_does_not_download(self):
        code, events = self.run_fake(action="inspect")
        self.assertEqual(code, 0)
        self.assertEqual(events[-1], {"type": "done", "files": [], "action": "inspect"})

    def test_live_video_does_not_download(self):
        code, events = self.run_fake(live=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["type"], "error")

    def test_missing_output_is_not_reported_as_success(self):
        code, events = self.run_fake(make_file=False)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["type"], "error")

    def test_real_subprocess_protocol_on_invalid_url(self):
        result = subprocess.run([sys.executable, "engine.py"], input=json.dumps({"url": "bad"}) + "\n",
                                capture_output=True, encoding="utf-8", cwd=engine.ROOT, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["type"], "error")


class FormattingTests(unittest.TestCase):
    def test_unknown_and_long_duration(self):
        self.assertEqual(duration(None), "時間未知")
        self.assertEqual(duration(3661), "1:01:01")
        self.assertEqual(size(1024), "1.0 KB")


if __name__ == "__main__":
    unittest.main()
