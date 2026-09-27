# 驗證紀錄

於 2026-09-27，在 Windows / Python 3.13.15 驗證。

## Stream Desk 2

- 22 項單元與背景程序測試通過，包含 Bilibili BV／av、分 P 驗證、偽裝網域、平台資訊、播放清單拒絕及 b23.tv 重新導向。
- b23.tv 重新導向以模擬 HTTP 回應測試，驗證指定分 P、目標白名單、無效回應及重新導向次數上限；不宣稱已對真實 b23.tv 連結完成下載驗證。
- GUI 測試通過：1240／850 像素視窗的雙欄／單欄切換、卡片水平邊界、記錄收合、平台識別、輸入驗證、格式切換、進度、完成狀態、檔案不存在提示及背景程序取消。
- 最後補充的 GUI 檢查亦通過：長篇中英文影片標題、來源回報的解析度、未知檔案大小與剩餘時間，以及切換網址後清除舊的完成狀態與開啟檔案按鈕。
- 實際 Bilibili 測試：`BV1bK411W797?p=1`，選擇最高 480p，取得長度 90.314 秒的第一 P，成功下載影片及音訊並合併為 MKV。來源資訊當時回報最高可取得 720p，但本次測試只選擇最高 480p。
- 再次執行 YouTube 19 秒公開短片下載，影音合併與輸出檔存在檢查通過。
- 再次執行本機 HTTP 媒體下載與 MKV／MP3 轉換，兩種輸出均通過完整解碼檢查。
- 網路測試使用暫存資料夾，結束後自動清除測試媒體。

## 第一版驗證

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
# 需要連線 Bilibili，只下載指定分 P，完成後清除：
.\.venv\Scripts\python.exe tests\smoke_bilibili.py
```
