"""繁體中文 YouTube 下載器，Python / Tkinter 桌面介面。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine import QUALITIES, ROOT, normalize_url

BG, CARD, FG, MUTED, ACCENT = "#10151f", "#1a2231", "#f2f5fc", "#a8b6cc", "#70e0bc"
SETTINGS = ROOT / "settings.json"
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def size(value):
    if value is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024


def duration(value):
    if value is None:
        return "時間未知"
    seconds = max(0, int(value))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


class Downloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube 下載器 · Stream Desk")
        self.geometry(f"900x{min(920, self.winfo_screenheight() - 100)}")
        self.minsize(760, 600)
        self.configure(bg=BG)
        self.process = None
        self.events = queue.Queue()
        self.cancelled = False
        self.terminal_event = False
        self.closing = False
        self.last_files = []
        self.job_id = 0
        try:
            settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
            if not isinstance(settings, dict):
                settings = {}
        except (OSError, ValueError):
            settings = {}
        self.url = tk.StringVar()
        self.folder = tk.StringVar(value=settings.get("folder", str(ROOT / "downloads")))
        quality = settings.get("quality", "最高 1080p")
        self.quality = tk.StringVar(value=quality if quality in QUALITIES else "最高 1080p")
        self.mode = tk.StringVar(value="video")
        self.status = tk.StringVar(value="準備就緒 · 貼上網址，開始你的第一個下載")
        self.title_text = tk.StringVar(value="你的下一支影片，準備收藏。")
        self.detail = tk.StringVar(value="先讀取資訊可查看影片名稱、頻道與長度。")
        self.metrics = tk.StringVar(value="等待下載  ·  速度 —  ·  剩餘時間 —")
        self.percent = tk.StringVar(value="0%")
        self._style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def _style(self):
        self.option_add("*Font", "{Microsoft JhengHei UI} 10")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground="#263246", background="#263246",
                        foreground=FG, arrowcolor=FG, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", "#263246")],
                  foreground=[("readonly", FG), ("disabled", MUTED)])
        style.configure("Horizontal.TProgressbar", troughcolor="#2a3548", background=ACCENT,
                        bordercolor=CARD, lightcolor=ACCENT, darkcolor=ACCENT)

    def label(self, parent, text=None, **kwargs):
        return tk.Label(parent, text=text, bg=parent["bg"], fg=FG, anchor="w", **kwargs)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                         bg=ACCENT if primary else "#2a374c", fg=BG if primary else FG,
                         activebackground="#a2eed7" if primary else "#3b4a63",
                         activeforeground=BG if primary else FG, disabledforeground="#6a7a90",
                         padx=17, pady=9, cursor="hand2")

    def entry(self, parent, variable):
        return tk.Entry(parent, textvariable=variable, bg="#111a29", fg=FG,
                        insertbackground=ACCENT, relief="flat", highlightthickness=1,
                        highlightbackground="#35415a", highlightcolor=ACCENT,
                        disabledbackground="#192230", disabledforeground=MUTED)

    def _build(self):
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        page = tk.Frame(self.canvas, bg=BG, padx=30, pady=22)
        page_id = self.canvas.create_window(0, 0, window=page, anchor="nw")
        page.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.resize_page(page_id, event.width))
        self.bind_all("<MouseWheel>", self.scroll_page)
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x")
        self.label(top, "▶  STREAM DESK", font=("Segoe UI", 10, "bold"), foreground=ACCENT).pack(anchor="w")
        self.label(top, "YouTube 影片下載器", font=("Microsoft JhengHei UI", 25, "bold")).pack(anchor="w", pady=(8, 4))
        self.label(top, "影片與聲音，存到你想要的地方。", foreground=MUTED).pack(anchor="w")

        box = tk.Frame(page, bg=CARD, padx=22, pady=18)
        box.pack(fill="x", pady=(22, 14))
        self.label(box, "01  貼上影片網址", font=("Microsoft JhengHei UI", 11, "bold")).pack(anchor="w")
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", pady=(10, 7))
        self.url_entry = self.entry(row, self.url)
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=12)
        self.paste_button = self.button(row, "貼上", self.paste)
        self.paste_button.pack(side="left", padx=(8, 0))
        self.inspect_button = self.button(row, "讀取資訊", lambda: self.start("inspect"))
        self.inspect_button.pack(side="left", padx=(8, 0))
        self.label(box, "支援 youtube.com、youtu.be 與 Shorts · 每次下載一支影片", foreground=MUTED).pack(anchor="w")
        self.label(box, "02  選擇下載內容", font=("Microsoft JhengHei UI", 11, "bold")).pack(anchor="w", pady=(20, 8))
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x")
        self.radios = []
        for value, text in [("video", "影片 + 音訊（MKV）"), ("audio", "僅音訊（MP3）")]:
            radio = tk.Radiobutton(row, text=text, value=value, variable=self.mode,
                                   bg=CARD, fg=FG, selectcolor=BG, activebackground=CARD,
                                   activeforeground=ACCENT, command=self.mode_changed)
            radio.pack(side="left", padx=(0, 14))
            self.radios.append(radio)
        self.quality_box = ttk.Combobox(row, textvariable=self.quality, values=list(QUALITIES),
                                        state="readonly", width=17)
        self.quality_box.pack(side="right")
        self.format_hint = self.label(box, "MKV 保留來源畫質；解析度以影片實際提供的格式為準。", foreground=MUTED)
        self.format_hint.pack(anchor="w", pady=(7, 0))
        self.label(box, "03  儲存位置", font=("Microsoft JhengHei UI", 11, "bold")).pack(anchor="w", pady=(20, 8))
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x")
        self.folder_entry = self.entry(row, self.folder)
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=11)
        self.browse_button = self.button(row, "選擇資料夾", self.browse)
        self.browse_button.pack(side="left", padx=(8, 0))

        result = tk.Frame(page, bg=CARD, padx=22, pady=18)
        result.pack(fill="x")
        self.video_title_label = self.label(result, textvariable=self.title_text,
                                            font=("Microsoft JhengHei UI", 13, "bold"), wraplength=735)
        self.video_title_label.pack(fill="x")
        self.video_detail_label = self.label(result, textvariable=self.detail, foreground=MUTED, wraplength=735)
        self.video_detail_label.pack(fill="x", pady=(5, 14))
        row = tk.Frame(result, bg=CARD)
        row.pack(fill="x")
        self.status_label = self.label(row, textvariable=self.status, wraplength=640)
        self.status_label.pack(side="left", fill="x", expand=True)
        self.label(row, textvariable=self.percent, foreground=ACCENT, font=("Segoe UI", 14, "bold")).pack(side="right")
        self.progress = ttk.Progressbar(result, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(10, 8), ipady=3)
        self.label(result, textvariable=self.metrics, foreground=MUTED).pack(fill="x")

        row = tk.Frame(page, bg=BG)
        row.pack(fill="x", pady=16)
        self.download_button = self.button(row, "↓  開始下載", lambda: self.start("download"), True)
        self.download_button.pack(side="left")
        self.cancel_button = self.button(row, "取消", self.cancel)
        self.cancel_button.pack(side="left", padx=10)
        self.cancel_button.configure(state="disabled")
        self.button(row, "開啟下載資料夾", self.open_folder).pack(side="right")
        self.label(page, "詳細記錄", foreground=MUTED).pack(anchor="w", pady=(0, 5))
        log_frame = tk.Frame(page, bg=BG)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=4, bg="#0c111a", fg=MUTED, relief="flat",
                           font=("Microsoft JhengHei UI", 9), wrap="word", state="disabled", padx=10, pady=8)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.url_entry.focus_set()

    def scroll_page(self, event):
        if event.widget != self.log:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def resize_page(self, page_id, width):
        self.canvas.itemconfigure(page_id, width=width)
        self.video_title_label.configure(wraplength=max(300, width - 115))
        self.video_detail_label.configure(wraplength=max(300, width - 115))
        self.status_label.configure(wraplength=max(260, width - 200))

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", str(text) + "\n")
        if int(self.log.index("end-1c").split(".")[0]) > 700:
            self.log.delete("1.0", "150.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def paste(self):
        try:
            self.url.set(self.clipboard_get().strip())
        except tk.TclError:
            self.status.set("剪貼簿沒有可貼上的文字。")

    def browse(self):
        selected = filedialog.askdirectory(title="選擇下載資料夾", mustexist=True)
        if selected:
            self.folder.set(selected)

    def mode_changed(self):
        audio = self.mode.get() == "audio"
        self.quality_box.configure(state="disabled" if audio else "readonly")
        self.format_hint.configure(text="MP3 音訊，192 kbps；不受右側影片畫質設定影響。" if audio else
                                   "MKV 保留來源畫質；解析度以影片實際提供的格式為準。")

    def set_busy(self, busy):
        for widget in [self.url_entry, self.folder_entry, self.paste_button, self.inspect_button,
                       self.browse_button, self.download_button, *self.radios]:
            widget.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        self.quality_box.configure(state="disabled" if busy or self.mode.get() == "audio" else "readonly")

    def start(self, action):
        if self.process is not None:
            return
        try:
            url = normalize_url(self.url.get())
            if not self.folder.get().strip():
                raise ValueError("請選擇儲存位置。")
            folder = str(Path(self.folder.get()).expanduser().resolve())
        except (ValueError, OSError) as error:
            messagebox.showerror("請檢查輸入", str(error), parent=self)
            return
        self.folder.set(folder)
        config = dict(url=url, folder=folder, mode=self.mode.get(), quality=self.quality.get(), action=action)
        try:
            SETTINGS.write_text(json.dumps({"folder": folder, "quality": self.quality.get()},
                                           ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as error:
            self.append_log(f"無法儲存偏好設定：{error}")
        self.cancelled = self.terminal_event = False
        self.last_files = []
        self.job_id += 1
        self.progress.stop()
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(12)
        self.percent.set("…")
        self.status.set("正在連線…")
        self.title_text.set("正在讀取影片…")
        self.detail.set("請稍候")
        self.metrics.set("等待下載  ·  速度 —  ·  剩餘時間 —")
        self.set_busy(True)
        try:
            executable = Path(sys.executable)
            if executable.name.lower() == "pythonw.exe":
                executable = executable.with_name("python.exe")
            process = subprocess.Popen([str(executable), "-u", str(ROOT / "engine.py")],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                                       creationflags=HIDDEN, start_new_session=os.name != "nt")
            self.process = process
            process.stdin.write(json.dumps(config, ensure_ascii=False) + "\n")
            process.stdin.close()
            threading.Thread(target=self.read_worker, args=(process, self.job_id), daemon=True).start()
        except OSError as error:
            if self.process is not None:
                self.process.kill()
                self.process.wait()
            self.process = None
            self.progress.stop()
            self.set_busy(False)
            self.status.set("啟動失敗")
            messagebox.showerror("無法啟動下載", str(error), parent=self)

    def read_worker(self, process, job_id):
        for line in process.stdout:
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("Not an event")
            except ValueError:
                event = {"type": "log", "text": line.rstrip()}
            self.events.put((job_id, event))
        process.stdout.close()
        code = process.wait()
        self.events.put((job_id, {"type": "exit", "code": code}))

    def poll(self):
        for _ in range(200):
            try:
                job_id, event = self.events.get_nowait()
            except queue.Empty:
                break
            if job_id != self.job_id:
                continue
            kind = event.get("type")
            if kind == "exit":
                self.process = None
                self.progress.stop()
                self.set_busy(False)
                if self.cancelled:
                    self.status.set("已取消 · 再次下載同一影片可接續部分下載")
                    self.percent.set("—")
                elif not self.terminal_event:
                    self.status.set("下載程序意外結束，請查看詳細記錄。")
                    self.percent.set("—")
                if self.closing:
                    self.destroy()
                    return
            elif kind == "cancel_error":
                self.cancelled = False
                self.closing = False
                self.cancel_button.configure(state="normal")
                self.append_log(event["text"])
                self.status.set("取消失敗，請再試一次。")
            elif self.cancelled:
                continue
            elif kind == "log":
                self.append_log(event["text"])
            elif kind == "info":
                self.title_text.set(event["title"])
                self.detail.set(f"{event['channel']}  ·  {duration(event.get('duration'))}")
            elif kind == "status":
                self.status.set(event["text"])
                self.progress.stop()
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
                self.percent.set("…")
            elif kind == "progress":
                percent = event.get("percent")
                if percent is not None:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=percent)
                    self.percent.set(f"{percent:.0f}%")
                self.status.set("正在下載串流（影片與音訊可能分別下載）…")
                self.metrics.set(f"{size(event['downloaded'])} / {size(event.get('total') or None)}  ·  "
                                 f"{size(event.get('speed'))}/s  ·  剩餘 {duration(event.get('eta'))}")
            elif kind == "done":
                self.terminal_event = True
                self.progress.stop()
                self.progress.configure(mode="determinate", value=100 if event["action"] == "download" else 0)
                self.last_files = event["files"]
                self.percent.set("100%" if self.last_files else "就緒")
                self.status.set("下載完成！可開啟下載資料夾查看。" if self.last_files else "影片資訊已就緒，可以開始下載。")
                if self.last_files:
                    self.metrics.set("已完成下載與處理")
                    for path in self.last_files:
                        self.append_log("已儲存：" + path)
            elif kind == "error":
                self.terminal_event = True
                self.progress.stop()
                self.percent.set("—")
                self.status.set("無法完成，請查看錯誤訊息後重試。")
                self.append_log(event["text"])
                messagebox.showerror("下載未完成", event["text"], parent=self)
        self.after(100, self.poll)

    def cancel(self):
        process = self.process
        if process is None or process.poll() is not None:
            return
        self.cancelled = True
        self.cancel_button.configure(state="disabled")
        self.status.set("正在取消並停止處理程序…")
        threading.Thread(target=self.stop_worker, args=(process, self.job_id), daemon=True).start()

    def stop_worker(self, process, job_id):
        try:
            if os.name == "nt":
                result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                        capture_output=True, creationflags=HIDDEN, timeout=15)
                if result.returncode and process.poll() is None:
                    raise RuntimeError("Windows 未能停止下載程序。")
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            if process.poll() is None:
                self.events.put((job_id, {"type": "cancel_error", "text": str(error)}))

    def open_folder(self):
        try:
            path = Path(self.folder.get()).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except OSError as error:
            messagebox.showerror("無法開啟資料夾", str(error), parent=self)

    def close(self):
        if self.process is not None:
            if not messagebox.askyesno("關閉下載器", "下載或讀取仍在進行。要取消並關閉嗎？", parent=self):
                return
            self.closing = True
            self.cancel()
        else:
            self.destroy()


if __name__ == "__main__":
    Downloader().mainloop()
