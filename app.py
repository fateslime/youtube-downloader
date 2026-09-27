"""Stream Desk 2 — YouTube / Bilibili desktop download workspace."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine import QUALITIES, ROOT, normalize_url, platform_name

BG, CARD, FG, MUTED, ACCENT = "#f3f5fa", "#ffffff", "#192238", "#738099", "#7054e8"
LINE, SOFT, NAV, SUCCESS = "#e5e9f2", "#f1edff", "#151b2e", "#178365"
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
        self.title("Stream Desk · YouTube & Bilibili 下載器")
        self.geometry(f"{min(1240, self.winfo_screenwidth() - 40)}x{min(900, self.winfo_screenheight() - 70)}")
        self.minsize(800, 620)
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
        self.status = tk.StringVar(value="貼上影片連結，即可開始。")
        self.title_text = tk.StringVar(value="下一支精彩，等你收藏。")
        self.detail = tk.StringVar(value="解析後顯示影片名稱、創作者與長度。")
        self.metrics = tk.StringVar(value="等待下載  ·  速度 —  ·  剩餘時間 —")
        self.percent = tk.StringVar(value="0%")
        self.platform = tk.StringVar(value="自動辨識平台")
        self.phase = tk.StringVar(value="準備就緒")
        self.speed_text = tk.StringVar(value="—")
        self.eta_text = tk.StringVar(value="—")
        self.amount_text = tk.StringVar(value="—")
        self.file_text = tk.StringVar(value="完成的檔案會顯示在這裡")
        self.availability = tk.StringVar(value="依來源提供的格式選擇畫質")
        self.log_visible = False
        self.busy = False
        self.layout_wide = None
        self._style()
        self._build()
        self.mode_changed()
        self.after_idle(lambda: self.canvas.yview_moveto(0))
        self.url.trace_add("write", self.update_platform)
        self.bind("<Control-Return>", lambda event: self.start("download"))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def _style(self):
        self.app_icon = tk.PhotoImage(width=32, height=32)
        self.app_icon.put(ACCENT, to=(0, 0, 32, 32))
        for row in range(8, 25):
            self.app_icon.put("white", to=(11, row, 12 + min(row - 8, 24 - row), row + 1))
        self.iconphoto(True, self.app_icon)
        self.option_add("*Font", "{Microsoft JhengHei UI} 10")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG, background=BG,
                        foreground=FG, arrowcolor=MUTED, bordercolor=LINE, padding=8)
        style.map("TCombobox", fieldbackground=[("readonly", BG)],
                  foreground=[("readonly", FG), ("disabled", MUTED)])
        style.configure("Vertical.TScrollbar", background=LINE, troughcolor=BG, borderwidth=0,
                        arrowcolor=MUTED, width=10)
        style.configure("Horizontal.TProgressbar", troughcolor=LINE, background=ACCENT,
                        bordercolor=CARD, lightcolor=ACCENT, darkcolor=ACCENT)

    def label(self, parent, text=None, **kwargs):
        options = dict(bg=parent["bg"], fg=FG, anchor="w", justify="left")
        options.update(kwargs)
        return tk.Label(parent, text=text, **options)

    def button(self, parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, relief="flat", bd=0,
                         bg=ACCENT if primary else SOFT, fg="white" if primary else ACCENT,
                         activebackground="#5c40d2" if primary else "#e4dcff",
                         activeforeground="white" if primary else ACCENT, disabledforeground="#a2aabd",
                         padx=14, pady=10, cursor="hand2", font=("Microsoft JhengHei UI", 10, "bold"))

    def entry(self, parent, variable):
        return tk.Entry(parent, textvariable=variable, bg=BG, fg=FG,
                        insertbackground=ACCENT, relief="flat", highlightthickness=1,
                        highlightbackground=LINE, highlightcolor=ACCENT,
                        disabledbackground=BG, disabledforeground=MUTED)

    def _build(self):
        sidebar = tk.Frame(self, bg=NAV, width=188, padx=18, pady=26)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        mark = tk.Canvas(sidebar, bg=NAV, width=40, height=42, highlightthickness=0)
        mark.pack(anchor="w", pady=(0, 10))
        mark.create_rectangle(1, 1, 39, 39, fill=ACCENT, outline=ACCENT)
        mark.create_polygon(15, 10, 15, 30, 29, 20, fill="white")
        self.label(sidebar, "Stream Desk", fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.label(sidebar, "影音下載工作空間", fg="#9ca8c2", font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(3, 34))
        self.label(sidebar, "WORKSPACE", fg="#697591", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 12))
        nav_button = self.button(sidebar, "↓  下載工作台", lambda: self.canvas.yview_moveto(0))
        nav_button.configure(bg="#302b53", fg="#d9ceff", anchor="w", padx=12)
        nav_button.pack(fill="x", pady=(0, 7))
        for text, command in [("▤  下載資料夾", self.open_folder), ("?  使用說明", self.show_help)]:
            button = self.button(sidebar, text, command)
            button.configure(bg=NAV, fg="#abb7ce", anchor="w", padx=12, font=("Microsoft JhengHei UI", 10))
            button.pack(fill="x", pady=3)
        bottom = tk.Frame(sidebar, bg=NAV)
        bottom.pack(side="bottom", fill="x")
        self.label(bottom, "支援平台", fg="#697591", font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        self.label(bottom, "●  YouTube", fg="#f3979e", font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 5))
        self.label(bottom, "●  Bilibili", fg="#75cbe7", font=("Segoe UI", 10)).pack(anchor="w")
        self.label(bottom, "DESKTOP EDITION   /   2.0", fg="#697591", font=("Segoe UI", 8)).pack(anchor="w", pady=(28, 0))

        content = tk.Frame(self, bg=BG)
        content.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(content, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(content, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        page = tk.Frame(self.canvas, bg=BG, padx=28, pady=26)
        page_id = self.canvas.create_window(0, 0, window=page, anchor="nw")
        page.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.resize_page(page_id, event.width))
        self.bind_all("<MouseWheel>", self.scroll_page)
        top = tk.Frame(page, bg=BG)
        top.pack(fill="x")
        self.label(top, "MEDIA WORKSPACE", font=("Segoe UI", 9, "bold"), fg=ACCENT).pack(anchor="w")
        self.label(top, "下載工作台", font=("Microsoft JhengHei UI", 25, "bold")).pack(anchor="w", pady=(7, 5))
        self.label(top, "從喜歡的影片，到你的私人收藏。", fg=MUTED).pack(anchor="w")
        tags = tk.Frame(page, bg=BG)
        tags.pack(fill="x", pady=(16, 22))
        for text, color, fill in [("YouTube", "#c64654", "#fff0f1"), ("Bilibili", "#217b9a", "#e7f6fb"),
                                  ("影片 / 音訊", MUTED, "#e9edf5")]:
            self.label(tags, text, fg=color, bg=fill, padx=12, pady=5,
                       font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))

        self.columns = tk.Frame(page, bg=BG)
        self.columns.pack(fill="x")
        self.editor = box = tk.Frame(self.columns, bg=CARD, padx=22, pady=22,
                                     highlightthickness=1, highlightbackground=LINE)
        self.label(box, "建立下載", font=("Microsoft JhengHei UI", 14, "bold")).pack(anchor="w")
        self.label(box, "一個連結，保存影片或聲音。", fg=MUTED, font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(4, 23))
        source_row = tk.Frame(box, bg=CARD)
        source_row.pack(fill="x")
        self.label(source_row, "01  影片來源", font=("Microsoft JhengHei UI", 10, "bold")).pack(side="left")
        self.source_badge = self.label(source_row, textvariable=self.platform, fg=ACCENT,
                                      font=("Segoe UI", 9, "bold"))
        self.source_badge.pack(side="right")
        self.url_entry = self.entry(box, self.url)
        self.url_entry.pack(fill="x", pady=(10, 8), ipady=12)
        self.url_hint = self.label(box, "貼上 YouTube、Bilibili 或 b23.tv 連結", fg=MUTED,
                                  font=("Microsoft JhengHei UI", 9), wraplength=450)
        self.url_hint.pack(anchor="w")
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", pady=(12, 22))
        self.paste_button = self.button(row, "貼上", self.paste)
        self.paste_button.pack(side="left")
        self.inspect_button = self.button(row, "解析影片  ↗", lambda: self.start("inspect"))
        self.inspect_button.pack(side="right")
        tk.Frame(box, bg=LINE, height=1).pack(fill="x", pady=(0, 20))
        self.label(box, "02  下載設定", font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x")
        self.radios = []
        for value, text in [("video", "影片 + 音訊\nMKV 原始畫質"), ("audio", "僅下載音訊\nMP3 · 192 kbps")]:
            radio = tk.Radiobutton(row, text=text, value=value, variable=self.mode,
                                   bg=BG, fg=FG, selectcolor=SOFT, activebackground=SOFT,
                                   activeforeground=ACCENT, indicatoron=False, bd=0, relief="flat",
                                   selectimage=None, padx=12, pady=12, cursor="hand2",
                                   font=("Microsoft JhengHei UI", 10), command=self.mode_changed)
            radio.pack(side="left", fill="x", expand=True, padx=(0, 6) if value == "video" else (6, 0))
            self.radios.append(radio)
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x", pady=(16, 0))
        self.label(row, "畫質上限", fg=MUTED).pack(side="left")
        self.quality_box = ttk.Combobox(row, textvariable=self.quality, values=list(QUALITIES),
                                        state="readonly", width=18)
        self.quality_box.pack(side="right")
        self.format_hint = self.label(box, "MKV 保留原始畫質，實際解析度依影片來源。", fg=MUTED,
                                      wraplength=450, font=("Microsoft JhengHei UI", 9))
        self.format_hint.pack(anchor="w", pady=(10, 0))
        self.label(box, "03  儲存位置", font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w", pady=(23, 10))
        row = tk.Frame(box, bg=CARD)
        row.pack(fill="x")
        self.folder_entry = self.entry(row, self.folder)
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=11)
        self.browse_button = self.button(row, "變更", self.browse)
        self.browse_button.pack(side="left", padx=(8, 0))
        self.download_button = self.button(box, "↓   開始下載", lambda: self.start("download"), True)
        self.download_button.configure(pady=14, font=("Microsoft JhengHei UI", 12, "bold"))
        self.download_button.pack(fill="x", pady=(24, 9))
        self.label(box, "每次下載一支影片  ·  Ctrl + Enter 開始", fg=MUTED,
                   font=("Microsoft JhengHei UI", 8), anchor="center").pack(fill="x")

        self.result = result = tk.Frame(self.columns, bg=CARD, padx=22, pady=22,
                                        highlightthickness=1, highlightbackground=LINE)
        row = tk.Frame(result, bg=CARD)
        row.pack(fill="x")
        self.label(row, "本次下載", font=("Microsoft JhengHei UI", 12, "bold")).pack(side="left")
        self.phase_label = self.label(row, textvariable=self.phase, fg=SUCCESS, bg="#eaf7f2",
                                      padx=8, pady=4, font=("Microsoft JhengHei UI", 8))
        self.phase_label.pack(side="right")
        cover = tk.Frame(result, bg=SOFT, padx=18, pady=18)
        cover.pack(fill="x", pady=(18, 18))
        self.preview_symbol = self.label(cover, "▷", fg=ACCENT, font=("Segoe UI", 36), anchor="center")
        self.preview_symbol.pack(fill="x")
        self.label(cover, textvariable=self.platform, fg=ACCENT, font=("Segoe UI", 9, "bold"),
                   anchor="center").pack(fill="x", pady=(3, 0))
        self.video_title_label = self.label(result, textvariable=self.title_text,
                                            font=("Microsoft JhengHei UI", 13, "bold"), wraplength=290)
        self.video_title_label.pack(fill="x")
        self.video_detail_label = self.label(result, textvariable=self.detail, fg=MUTED, wraplength=290,
                                             font=("Microsoft JhengHei UI", 9))
        self.video_detail_label.pack(fill="x", pady=(5, 14))
        self.available_label = self.label(result, textvariable=self.availability, fg=MUTED,
                                          font=("Microsoft JhengHei UI", 8), wraplength=290)
        self.available_label.pack(fill="x", pady=(0, 18))
        tk.Frame(result, bg=LINE, height=1).pack(fill="x", pady=(0, 18))
        steps = tk.Frame(result, bg=CARD)
        steps.pack(fill="x", pady=(0, 16))
        self.phase_labels = []
        for text in ("1  解析", "2  下載", "3  處理"):
            label = self.label(steps, text, fg=MUTED, font=("Microsoft JhengHei UI", 9), anchor="center")
            label.pack(side="left", expand=True, fill="x")
            self.phase_labels.append(label)
        row = tk.Frame(result, bg=CARD)
        row.pack(fill="x")
        self.status_label = self.label(row, textvariable=self.status, wraplength=235,
                                       font=("Microsoft JhengHei UI", 9))
        self.status_label.pack(side="left", fill="x", expand=True)
        self.label(row, textvariable=self.percent, fg=ACCENT, font=("Segoe UI", 15, "bold")).pack(side="right", padx=(10, 0))
        self.progress = ttk.Progressbar(result, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(10, 8), ipady=3)
        stats = tk.Frame(result, bg=CARD)
        stats.pack(fill="x", pady=(10, 20))
        for title, variable in [("已下載", self.amount_text), ("速度", self.speed_text), ("剩餘時間", self.eta_text)]:
            column = tk.Frame(stats, bg=CARD)
            column.pack(side="left", fill="x", expand=True)
            self.label(column, title, fg=MUTED, font=("Microsoft JhengHei UI", 8)).pack(anchor="w")
            self.label(column, textvariable=variable, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(5, 0))
        self.cancel_button = self.button(result, "取消本次工作", self.cancel)
        self.cancel_button.pack(fill="x")
        self.cancel_button.configure(state="disabled")
        self.file_label = self.label(result, textvariable=self.file_text, fg=MUTED, wraplength=290,
                                    font=("Microsoft JhengHei UI", 8))
        self.file_label.pack(fill="x", pady=(15, 8))
        self.open_button = self.button(result, "開啟完成的檔案  ↗", self.open_file)
        self.open_button.configure(state="disabled")
        self.open_button.pack(fill="x")

        footer = tk.Frame(page, bg=BG)
        footer.pack(fill="x", pady=(18, 0))
        self.log_button = self.button(footer, "＋  詳細記錄", self.toggle_log)
        self.log_button.configure(bg=BG, fg=MUTED, padx=0, font=("Microsoft JhengHei UI", 9))
        self.log_button.pack(side="left")
        self.label(footer, "STREAM DESK  /  2.0", fg=MUTED, font=("Segoe UI", 8)).pack(side="right")
        self.log_frame = log_frame = tk.Frame(page, bg=BG)
        self.log = tk.Text(log_frame, height=7, bg="#e9edf5", fg="#52617a", relief="flat",
                           font=("Microsoft JhengHei UI", 9), wrap="word", state="disabled", padx=10, pady=8)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.layout_cards(950)
        self.url_entry.focus_set()

    def scroll_page(self, event):
        if event.widget != self.log:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def resize_page(self, page_id, width):
        self.canvas.itemconfigure(page_id, width=width)
        if not hasattr(self, "video_title_label"):
            return
        self.layout_cards(width - 56)

    def layout_cards(self, width):
        wide = width >= 760
        if wide != self.layout_wide:
            self.layout_wide = wide
            self.editor.grid_forget()
            self.result.grid_forget()
            self.columns.columnconfigure(0, weight=3, minsize=0)
            self.columns.columnconfigure(1, weight=2 if wide else 0, minsize=0)
            self.editor.grid(row=0, column=0, sticky="new", padx=(0, 18 if wide else 0))
            self.result.grid(row=0 if wide else 1, column=1 if wide else 0, sticky="new",
                             pady=(0, 0) if wide else (18, 0))
        # Give grids explicit proportions instead of allowing long titles to dictate widths.
        editor_width = int((width - 18) * 0.57) if wide else width
        result_width = width - editor_width - 18 if wide else width
        self.editor.configure(width=editor_width)
        self.result.configure(width=result_width)
        self.columns.columnconfigure(0, minsize=editor_width + (18 if wide else 0))
        self.columns.columnconfigure(1, minsize=result_width if wide else 0)
        for label in (self.video_title_label, self.video_detail_label, self.available_label, self.file_label):
            label.configure(wraplength=max(230, result_width - 48))
        self.status_label.configure(wraplength=max(150, result_width - 120))
        self.format_hint.configure(wraplength=max(280, editor_width - 48))
        self.url_hint.configure(wraplength=max(280, editor_width - 48))

    def toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_frame.pack(fill="x", pady=(8, 0))
        else:
            self.log_frame.pack_forget()
        self.log_button.configure(text="−  收合詳細記錄" if self.log_visible else "＋  詳細記錄")

    def update_platform(self, *_):
        try:
            platform = platform_name(normalize_url(self.url.get()))
        except ValueError:
            platform = "自動辨識平台"
        self.platform.set(platform)
        self.source_badge.configure(fg="#217b9a" if platform == "Bilibili" else ACCENT)
        if not self.busy:
            self.last_files = []
            self.open_button.configure(state="disabled")
            self.file_text.set("完成的檔案會顯示在這裡")
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.percent.set("0%")
            self.status.set("貼上影片連結，即可開始。")
            self.set_phase("idle")
            for variable in (self.amount_text, self.speed_text, self.eta_text):
                variable.set("—")
            self.title_text.set("下一支精彩，等你收藏。")
            self.detail.set("解析後顯示影片名稱、創作者與長度。")
            self.availability.set("Bilibili 支援指定分 P，例如 ?p=2" if platform == "Bilibili" else
                                  "依來源提供的格式選擇畫質")

    def set_phase(self, phase):
        labels = {"idle": "準備就緒", "inspect": "解析中", "download": "下載中", "process": "處理中",
                  "ready": "已解析", "done": "已完成", "error": "未完成", "cancelled": "已取消"}
        self.phase.set(labels.get(phase, phase))
        color = "#bc4354" if phase == "error" else SUCCESS if phase in {"done", "ready", "idle"} else ACCENT
        self.phase_label.configure(fg=color, bg="#fff0f1" if phase == "error" else "#eaf7f2" if color == SUCCESS else SOFT)
        active = {"inspect": 0, "ready": 0, "download": 1, "process": 2, "done": 3}.get(phase, -1)
        for index, label in enumerate(self.phase_labels):
            label.configure(fg=SUCCESS if index < active else ACCENT if index == active else MUTED)
        self.preview_symbol.configure(text="✓" if phase == "done" else "!" if phase == "error" else "▷")

    def show_help(self):
        messagebox.showinfo("使用 Stream Desk", "1. 貼上 YouTube 或 Bilibili 單支影片網址。\n"
                            "2. 可先解析影片，再選擇畫質與 MKV／MP3。\n"
                            "3. 選擇儲存位置並開始下載。\n\n"
                            "Bilibili 支援 BV／av、b23.tv 與 ?p=2 指定分 P。\n"
                            "未指定分 P 時下載第一 P，不會下載整份播放清單。\n"
                            "來源需要登入或會員資格時，可能無法下載或取得高畫質。", parent=self)

    def open_file(self):
        if not self.last_files:
            return
        path = Path(self.last_files[-1])
        if not path.is_file():
            messagebox.showerror("找不到檔案", "檔案可能已移動或刪除，請開啟下載資料夾查看。", parent=self)
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except OSError as error:
            messagebox.showerror("無法開啟檔案", str(error), parent=self)

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", datetime.now().strftime("%H:%M:%S") + "  " + str(text) + "\n")
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
                                   "MKV 保留原始畫質，實際解析度依影片來源。")
        for radio in self.radios:
            selected = radio["value"] == self.mode.get()
            radio.configure(fg=ACCENT if selected else MUTED)

    def set_busy(self, busy):
        self.busy = busy
        for widget in [self.url_entry, self.folder_entry, self.paste_button, self.inspect_button,
                       self.browse_button, self.download_button, *self.radios]:
            widget.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        self.download_button.configure(text="正在處理…" if busy else "↓   開始下載")
        self.open_button.configure(state="normal" if self.last_files and not busy else "disabled")
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
        self.file_text.set("完成的檔案會顯示在這裡")
        self.platform.set(platform_name(url))
        self.availability.set("正在取得可用畫質…")
        self.speed_text.set("—")
        self.eta_text.set("—")
        self.amount_text.set("—")
        self.set_phase("inspect")
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
            self.set_phase("error")
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
                    self.set_phase("cancelled")
                elif not self.terminal_event:
                    self.status.set("下載程序意外結束，請查看詳細記錄。")
                    self.percent.set("—")
                    self.set_phase("error")
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
                if event.get("platform"):
                    self.platform.set(event["platform"])
                height = event.get("max_height")
                self.availability.set(f"目前可取得最高 {height}p" if height else "已取得來源提供的格式")
            elif kind == "status":
                self.status.set(event["text"])
                self.set_phase(event.get("phase", "process"))
                self.progress.stop()
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
                self.percent.set("…")
            elif kind == "progress":
                self.set_phase("download")
                percent = event.get("percent")
                if percent is not None:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=percent)
                    self.percent.set(f"{percent:.0f}%")
                else:
                    self.progress.stop()
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(12)
                    self.percent.set("…")
                self.status.set("正在下載影音串流…")
                self.amount_text.set(size(event["downloaded"]))
                self.speed_text.set(f"{size(event['speed'])}/s" if event.get("speed") else "—")
                self.eta_text.set(duration(event.get("eta")) if event.get("eta") is not None else "—")
                self.metrics.set(f"{size(event['downloaded'])} / {size(event.get('total') or None)}  ·  "
                                 f"{size(event.get('speed'))}/s  ·  剩餘 {duration(event.get('eta'))}")
            elif kind == "done":
                self.terminal_event = True
                self.progress.stop()
                self.progress.configure(mode="determinate", value=100 if event["action"] == "download" else 0)
                self.last_files = event["files"]
                self.percent.set("100%" if self.last_files else "就緒")
                self.set_phase("done" if self.last_files else "ready")
                self.status.set("下載完成！可開啟下載資料夾查看。" if self.last_files else "影片資訊已就緒，可以開始下載。")
                if self.last_files:
                    self.file_text.set(Path(self.last_files[-1]).name)
                    self.speed_text.set("—")
                    self.eta_text.set("已完成")
                    self.metrics.set("已完成下載與處理")
                    for path in self.last_files:
                        self.append_log("已儲存：" + path)
            elif kind == "error":
                self.terminal_event = True
                self.progress.stop()
                self.percent.set("—")
                self.set_phase("error")
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
