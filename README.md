# YouTube 影片下載器 · Stream Desk

使用 Python、Tkinter、yt-dlp 製作的繁體中文桌面下載器。

## 助教閱讀入口

這個儲存庫保存 AI 協作作業的程式碼、安裝方式與測試紀錄。請依以下順序閱讀：

1. [AI 協作與成果說明](AI_COLLABORATION.md)：原始提示詞、實際分工、修正過程與功能範圍。
2. [介面程式 app.py](app.py) 與 [下載引擎 engine.py](engine.py)：完整程式碼及註解。
3. [測試紀錄](TESTING.md)：已執行的檢查、結果，以及實際下載與模擬測試的區別。
4. [自動化測試](tests/test_downloader.py)：網址、格式選擇、錯誤處理與背景程序通訊測試。

報告引用時，請同時提供儲存庫首頁與固定 commit 版本連結，讓後續修改不影響繳交版本。GitHub 連結能否替代 Word 中的完整程式碼，仍依課程規定辦理。

第一次使用 GitHub，可參考 [本專案 GitHub 入門](GITHUB_GUIDE.md)。

## Windows 使用方式

1. 雙擊 **start.bat**。
2. 貼上 YouTube 單支影片網址，也支援 youtu.be、Shorts 及已結束的直播。
3. 可先按「讀取資訊」確認影片名稱、頻道與長度，也可以直接下載。
4. 選擇「影片 + 音訊（MKV）」或「僅音訊（MP3）」，設定畫質及儲存資料夾。
5. 按「開始下載」。完成後按「開啟下載資料夾」。

首次啟動會自動建立 `.venv` 並安裝依賴；本機若沒有 Python，需要先安裝 Python 3.10 以上版本（含 Tcl/Tk），或安裝 uv 讓設定程式下載 Python。已配置好的環境可直接使用。預設儲存於本專案的 `downloads`；會記住你選擇的資料夾和畫質。

## 功能與格式

- 繁體中文深色桌面介面、影片資訊、進度、速度與剩餘時間。
- 影片：最佳畫質、最高 4K、1440p、1080p、720p、480p。
- MKV 容器保留原始編碼，不額外壓縮；播放器須支援影片來源的編碼。畫質是上限，實際以影片提供的格式為準。
- 音訊：轉成 192 kbps MP3；這不會提升來源音訊的品質。
- 高畫質影片與音訊可能分開下載，各自顯示串流進度，再自動合併。
- 下載與轉檔在背景子程序執行；「取消」會停止這項工作的程序樹。
- 中途取消保留 `.part` 等暫存檔，再選擇相同資料夾、影片及設定時可嘗試續傳。
- 不覆寫已完成的同名檔案；檔名包含影片 ID，減少不同影片同名衝突。
- 不支援整份播放清單、進行中的直播、未開始的首播或需要登入的影片。

## 安裝與更新

Windows 可執行 `setup.ps1` 安裝，或雙擊 **update.bat** 更新依賴。YouTube 規則變更導致下載失敗時，可先關閉程式後執行 update.bat。

手動安裝：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

依賴包含 yt-dlp 的 EJS 元件、Deno JavaScript runtime，以及 imageio-ffmpeg 隨附的 FFmpeg，不需另外修改系統 PATH。完整 YouTube 支援需要 EJS 和 JavaScript runtime，影片合併與 MP3 轉檔需要 FFmpeg。參考 [yt-dlp 文件](https://github.com/yt-dlp/yt-dlp#dependencies)、[EJS 設定](https://github.com/yt-dlp/yt-dlp/wiki/EJS)。

## 開發與檔案

- `app.py`：Tkinter 介面、程序管理與下載事件顯示。
- `engine.py`：網址驗證、格式選擇、yt-dlp 背景下載工作。
- `settings.json`：本機偏好設定，自動建立。
- `tests/test_downloader.py`：網址驗證、格式、背景工作與程序通訊測試。
- `tests/smoke_gui.py`：實際視窗、進度顯示與背景程序取消測試。
- `tests/smoke_media.py`：本機測試媒體下載、MKV 封裝與 MP3 轉換。
- `tests/smoke_youtube.py`：連線 YouTube 的公開短片下載測試。
- `.runtime` / `.venv` / `.cache`：本機執行環境與快取，無需提交版本控制。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

若雙擊無法開啟，從 PowerShell 執行 `.\.venv\Scripts\python.exe app.py` 可查看錯誤。影片被刪除、限區或 YouTube 要求登入／額外驗證時，程式會顯示錯誤原因，無法保證每支影片都可下載。
