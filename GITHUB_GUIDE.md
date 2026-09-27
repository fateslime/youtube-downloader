# 使用本專案學習 GitHub

## Git 與 GitHub 的分工

Git 在電腦上記錄檔案的版本。GitHub 儲存推送到網路的版本，提供閱讀、下載、討論與協作的介面。

| 名稱 | 在本專案中的意思 |
| --- | --- |
| Repository 儲存庫 | 下載器的程式碼、說明和版本歷史。 |
| Commit 提交 | 保存一組變更，附上說明及唯一識別碼。 |
| main 分支 | 本專案主要開發版本所在的分支。 |
| origin 遠端 | 這個本機專案所連接的 GitHub 儲存庫別名。 |
| Push 推送 | 將本機已提交的版本上傳 GitHub。 |
| Clone 複製 | 取得 GitHub 儲存庫及其 Git 歷史到電腦上。 |
| .gitignore | 指定不應加入版本管理的檔案，例如環境、快取和下載影片。 |

## 助教怎麼閱讀

儲存庫首頁會顯示 README。點擊 `app.py` 或 `engine.py` 即可閱讀程式碼；點擊檔案左側行號，可引用特定程式碼行。`TESTING.md` 說明已驗證的範圍，`AI_COLLABORATION.md` 說明開發過程。

需要執行時，可使用 Code 選單的 Download ZIP，解壓縮後依 README 安裝並執行。ZIP 不包含虛擬環境和影片，首次設定需下載依賴。

## 在 VS Code 記錄下一次修改

建議直接以 VS Code 開啟 `youtube-downloader` 資料夾，讓「原始檔控制」對應到這個專案。

1. 修改程式並儲存。
2. 開啟「原始檔控制」，點擊變更的檔案檢查差異。
3. 按檔案旁的 `+`，將要保存的變更加入暫存區。
4. 輸入能描述修改的提交訊息，例如「修正空白網址錯誤提示」，按 Commit。
5. 按 Push 或同步變更，把提交推送至 GitHub。首次操作可能需要 GitHub 登入。

Commit 只保存本機版本；Push 才會更新 GitHub。每次提交前先檢查差異，不要把其他專案或私人設定混入。

## 對應的命令列操作

在 `youtube-downloader` 資料夾開啟終端機：

```powershell
# 查看目前有哪些檔案變更
git status

# 查看尚未暫存的程式差異
git diff

# 只暫存這次修改的檔案；請依實際修改調整檔名
git add app.py engine.py

# 檢查即將提交的內容
git diff --cached

# 保存版本
git commit -m "Improve download status messages"

# 上傳已保存的版本
git push origin main
```

## 為報告取得固定版本連結

儲存庫首頁顯示最新內容，適合作為閱讀入口。報告還應附上繳交時的 commit 連結或以該 commit 為基準的程式碼連結。

1. 在 GitHub 打開要引用的程式碼檔案。
2. 按鍵盤 `y`，將網址從分支名稱改成 commit 識別碼。
3. 複製這個永久連結貼入報告。
4. 也可以在本機執行 `git rev-parse HEAD` 取得目前 commit 識別碼。

之後再改程式，不會改變這個 commit 所保存的內容。每一輪迭代都可以建立新的 commit，再把對應連結填入報告；不要拿同一個最新版本網址假裝是不同輪的程式碼。

報告可使用：

> AI 回應的完整程式碼已保存於 GitHub。儲存庫首頁提供功能說明、安裝方法及檔案索引；固定版本連結對應本次提交內容。主要檔案為 app.py 與 engine.py，測試紀錄見 TESTING.md。各輪實際提示詞與修改過程見 AI_COLLABORATION.md。
>
> 儲存庫首頁：［貼上實際網址］
>
> 固定版本連結：［貼上實際 commit 或 tree 網址］
>
> Commit 識別碼：［貼上完整識別碼］

模板原本要求完整貼上程式碼，改用 GitHub 連結是否符合繳交方式，請依助教或課程要求辦理。

## 官方參考

- [建立儲存庫](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [取得檔案永久連結](https://docs.github.com/en/repositories/working-with-files/using-files/getting-permanent-links-to-files)
- [GitHub 入門練習](https://docs.github.com/en/get-started/start-your-journey/hello-world)
