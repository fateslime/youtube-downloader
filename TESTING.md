# 驗證紀錄

於 2026-09-27，在 Windows / Python 3.13.15 驗證。

- 12 項單元與程序通訊測試通過。
- Tkinter 視窗能建立，畫質／音訊切換、空網址錯誤、進度、完成状态均通過。
- 螢幕縮放下可捲動至詳細記錄，避免下方按鈕或內容被裁切。
- 取消操作可停止測試背景程序，恢復可下載狀態；取消失敗時能恢復重試按鈕。
- 本機 HTTP 媒體下載與 MKV 重新封裝通過；FFmpeg 可完整解碼輸出。
- 本機媒體下載與 192 kbps MP3 轉換通過；FFmpeg 可完整解碼輸出。
- YouTube 公開短片 `jNQXAC9IVRw`（19 秒）：影片資訊讀取、分開下載影音串流、FFmpeg 合併 MKV，以及輸出檔案存在檢查均通過。測試檔已自動清除。

測試依賴：yt-dlp 2026.8.19、yt-dlp-ejs 0.8.0、Deno 2.9.7、imageio-ffmpeg 0.6.0 隨附 FFmpeg 7.1。

測試不代表所有 YouTube 影片都可以下載；站方驗證、私人影片與地區限制仍可能使下載失敗。

執行方式（位於專案目錄）：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests\smoke_media.py
.\.venv\Scripts\python.exe tests\smoke_gui.py
# 需要連線 YouTube，產生暫存下載並在完成後清除：
.\.venv\Scripts\python.exe tests\smoke_youtube.py
```
