import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import engine
from app import duration, size


class UrlTests(unittest.TestCase):
    def test_bilibili_urls_and_part_are_preserved(self):
        pairs = {
            "https://www.bilibili.com/video/BV1bK411W797/?p=2&spm_id_from=test":
                "https://www.bilibili.com/video/BV1bK411W797?p=2",
            "https://m.bilibili.com/video/av1074402": "https://www.bilibili.com/video/av1074402",
            "BV1bK411W797": "https://www.bilibili.com/video/BV1bK411W797",
            "av1074402": "https://www.bilibili.com/video/av1074402",
            "https://b23.tv/abc123?share_source=copy": "https://b23.tv/abc123",
        }
        for value, expected in pairs.items():
            with self.subTest(value=value):
                self.assertEqual(engine.normalize_url(value), expected)
                self.assertEqual(engine.platform_name(expected), "Bilibili")

    def test_bilibili_rejects_invalid_parts_collections_and_lookalikes(self):
        for value in ["https://bilibili.com.evil.test/video/BV1bK411W797",
                      "https://b23.tv.evil.test/abc", "https://space.bilibili.com/123/video",
                      "https://bilibili.com/video/BV123", "https://bilibili.com/bangumi/play/ep123",
                      "https://bilibili.com/video/BV1bK411W797?p=0",
                      "https://bilibili.com/video/BV1bK411W797?p=-2",
                      "https://bilibili.com/video/BV1bK411W797?p=",
                      "https://bilibili.com/video/BV1bK411W797?p=2&p=3",
                      "https://bilibili.com/video/BV1bK411W797?p=2.5"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                engine.normalize_url(value)

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

    def test_bilibili_download_is_limited_to_one_video(self):
        options = engine.build_options({"url": "https://www.bilibili.com/video/BV1bK411W797?p=2"}, "ffmpeg", "deno")
        self.assertTrue(options["noplaylist"])


class ShortLinkTests(unittest.TestCase):
    def response(self, location, status=302):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = status
        response.headers = {"Location": location} if location else {}
        return response

    def test_resolves_short_link_and_keeps_selected_part(self):
        response = self.response("https://www.bilibili.com/video/BV1bK411W797?p=3&share=abc")
        with patch("requests.get", return_value=response) as request:
            url = engine.resolve_video_url("https://b23.tv/abc123?p=2")
        self.assertEqual(url, "https://www.bilibili.com/video/BV1bK411W797?p=2")
        self.assertFalse(request.call_args.kwargs["allow_redirects"])

    def test_untrusted_redirect_is_rejected_before_another_request(self):
        for target in ["https://example.org/file", "https://youtu.be/BaW_jenozKc"]:
            with patch("requests.get", return_value=self.response(target)) as request:
                with self.assertRaises(ValueError):
                    engine.resolve_video_url("https://b23.tv/abc123")
                self.assertEqual(request.call_count, 1)

    def test_redirect_loop_is_bounded(self):
        with patch("requests.get", return_value=self.response("https://b23.tv/abc123")) as request:
            with self.assertRaises(ValueError):
                engine.resolve_video_url("https://b23.tv/abc123")
            self.assertEqual(request.call_count, 5)

    def test_nonredirect_short_link_produces_helpful_error(self):
        with patch("requests.get", return_value=self.response(None, 200)):
            with self.assertRaisesRegex(ValueError, "完整的 BV"):
                engine.resolve_video_url("https://b23.tv/abc123")


class WorkerTests(unittest.TestCase):
    def run_fake(self, action="download", live=False, make_file=True, url="youtu.be/BaW_jenozKc", playlist=False):
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
                    if playlist:
                        return {"_type": "playlist", "entries": []}
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
                code = engine.run_worker({"url": url, "folder": folder, "action": action})
            return code, [json.loads(line) for line in buffer.getvalue().splitlines()]

    def test_bilibili_worker_reports_platform_and_keeps_part(self):
        url = "https://www.bilibili.com/video/BV1bK411W797?p=2"
        code, events = self.run_fake(url=url)
        self.assertEqual(code, 0)
        info = next(event for event in events if event["type"] == "info")
        self.assertEqual(info["platform"], "Bilibili")
        self.assertEqual(info["url"], url)

    def test_unexpected_playlist_is_rejected(self):
        code, events = self.run_fake(playlist=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["type"], "error")

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
    def test_bilibili_restriction_message_names_the_platform(self):
        self.assertIn("Bilibili", engine.friendly_error(Exception("HTTP Error 412"), "Bilibili"))
        self.assertIn("會員", engine.friendly_error(Exception("premium required"), "Bilibili"))

    def test_unknown_and_long_duration(self):
        self.assertEqual(duration(None), "時間未知")
        self.assertEqual(duration(3661), "1:01:01")
        self.assertEqual(size(1024), "1.0 KB")


if __name__ == "__main__":
    unittest.main()
