"""Create a real Tk window and exercise its asynchronous worker and state changes."""
from pathlib import Path
import sys
import time
import subprocess
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Downloader, HIDDEN


def main():
    app = Downloader()
    app.update()
    assert app.winfo_width() >= 800
    assert app.download_button.winfo_viewable()
    assert not app.log_visible
    app.toggle_log()
    app.update()
    assert app.log.winfo_height() >= 40
    region = app.canvas.bbox("all")
    assert region[3] >= app.log.winfo_y() + app.log.winfo_height()
    app.canvas.yview_moveto(1)
    app.update()
    assert app.log.winfo_rooty() + app.log.winfo_height() <= app.winfo_rooty() + app.winfo_height()
    app.canvas.yview_moveto(0)
    for width, wide in [(1240, True), (850, False)]:
        app.geometry(f"{width}x800")
        app.update()
        assert app.layout_wide == wide
        for card in (app.editor, app.result):
            right = card.winfo_rootx() + card.winfo_width()
            assert right <= app.canvas.winfo_rootx() + app.canvas.winfo_width(), (width, right)
    app.url.set("https://bilibili.com/video/BV1bK411W797?p=2")
    assert app.platform.get() == "Bilibili"
    app.url.set("https://youtu.be/jNQXAC9IVRw")
    assert app.platform.get() == "YouTube"
    app.url.set("")
    app.mode.set("audio")
    app.mode_changed()
    assert str(app.quality_box["state"]) == "disabled"
    app.mode.set("video")
    app.mode_changed()
    assert str(app.quality_box["state"]) == "readonly"
    with patch("app.messagebox.showerror") as error:
        app.start("download")
        assert error.called
    app.set_busy(True)
    assert str(app.download_button["state"]) == "disabled"
    app.set_busy(False)
    app.job_id = 1
    app.events.put((1, {"type": "info", "title": "A long bilingual video title 影片標題 " * 6,
                        "channel": "測試創作者", "duration": 90, "platform": "Bilibili", "max_height": 720}))
    app.poll()
    app.update()
    assert app.platform.get() == "Bilibili"
    assert "720p" in app.availability.get()
    assert app.video_title_label.winfo_width() <= app.result.winfo_width()
    app.events.put((1, {"type": "progress", "percent": None, "downloaded": 100,
                        "total": 0, "speed": None, "eta": None}))
    app.poll()
    assert app.percent.get() == "…" and app.eta_text.get() == "—"
    app.events.put((1, {"type": "progress", "percent": 50, "downloaded": 1024, "total": 2048,
                        "speed": 100, "eta": 10}))
    app.poll()
    assert app.percent.get() == "50%"
    app.events.put((1, {"type": "done", "files": ["sample.mkv"], "action": "download"}))
    app.events.put((1, {"type": "exit", "code": 0}))
    app.poll()
    assert app.percent.get() == "100%"
    assert app.phase.get() == "已完成"
    assert str(app.open_button["state"]) == "normal"
    with patch("app.messagebox.showerror") as error:
        app.open_file()
        assert error.called
    assert str(app.download_button["state"]) == "normal"
    app.cancelled = True
    app.events.put((1, {"type": "cancel_error", "text": "test retry"}))
    app.poll()
    assert not app.cancelled
    assert str(app.cancel_button["state"]) == "normal"
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", creationflags=HIDDEN)
    app.process = process
    app.job_id = 2
    app.set_busy(True)
    threading.Thread(target=app.read_worker, args=(process, 2), daemon=True).start()
    app.cancel()
    deadline = time.monotonic() + 20
    while app.process is not None and time.monotonic() < deadline:
        app.update()
        time.sleep(0.02)
    assert app.process is None and process.poll() is not None
    assert "已取消" in app.status.get()
    app.url.set("https://bilibili.com/video/BV1bK411W797")
    assert app.phase.get() == "準備就緒"
    assert not app.last_files and str(app.open_button["state"]) == "disabled"
    app.destroy()
    print("PASS GUI: responsive layout, platform detection, validation, format controls, progress, completed file and process cancellation")


if __name__ == "__main__":
    main()
