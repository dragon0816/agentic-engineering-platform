# 發佈 Windows 安裝包給同事

給負責發佈的人看。同事端怎麼安裝、更新，寫在安裝包裡的
`deploy/windows-preview/INSTALL.zh-TW.md`。

## 一個指令產生交付版本

修改並 commit 之後，在 repo 根目錄執行：

```powershell
scripts\release.cmd
# 產生後同時複製到共用資料夾（例如團隊 OneDrive）：
scripts\release.cmd --publish-dir "C:\Users\<你>\OneDrive - Rohde & Schwarz\AEP releases"
```

腳本（`scripts/release_windows.py`）依序執行，任何一步失敗就停止，不會產生半成品：

1. **檢查有沒有沒 commit 的修改。** 安裝包從 commit 好的版本（`git archive HEAD`）建置，
   所以同事裝到的內容，正好是版本碼對應的那個 commit。
   還沒 commit 的修改會被擋下；硬要發佈可以加 `--allow-dirty`，但那些修改**不會**被打包。
2. **驗證**：ruff、mypy、完整測試，約 15 分鐘。
   - `--quick` 跳過測試；
   - `--skip-checks` 三項都跳過，只建議用在同一版本重新打包。
3. **建置 wheel**：從匯出的程式碼建出平台 wheel，並下載 64 位元 Windows、
   Python 3.12 用的相依套件。套件清單和 CI 相同，由測試保證兩邊一致。
4. **打包**：用 `scripts/build_windows_preview.py` 產生離線安裝包。每個檔案都有 SHA-256，
   也會檢查路徑長度，並確認沒有夾帶疑似密碼的內容。
5. **建立發佈資料夾** `dist/releases/<日期時間>-<版本碼>/`，內含：
   - `aep-windows-preview-0.1.0-<版本碼>.zip`：安裝包；
   - `SHA256SUMS.txt`：同事可以用來比對 zip 是否完整；
   - `RELEASE_NOTES.md`：上次發佈以來的 commit 清單；
   - `INSTALL.zh-TW.md`：安裝手冊，不必解壓縮就能看。

   `dist/releases/latest.json` 記錄這次的版本碼，下次的發佈說明就從這裡接著列。
6. **打 git tag**：在該 commit 建立 annotated tag `release-<日期時間>-<版本碼>`，
   tag 訊息記錄 zip 名稱和 SHA-256。同事回報版本碼時，用 `git show <tag>` 就能找到對應的
   原始碼。tag 只建在本機；要讓團隊看到，自己執行 `git push origin <tag>`。
   加 `--no-tag` 可以不打 tag。
7. **（選用）`--publish-dir`**：把整個發佈資料夾複製過去，不會刪除或覆蓋舊版本。

## 交付給同事

- 把發佈資料夾（或 `--publish-dir` 那份）的位置告訴同事，並附上 `RELEASE_NOTES.md` 的
  重點。
- 第一次安裝：`install.cmd`；之後更新：`update.cmd`（設定、workspace 和對話都會保留）。
- 同事回報問題時，請他提供 `verify.cmd` 顯示的版本碼，再用 `git tag --contains <版本碼>`
  或 `git show release-...` 找到對應的發佈和原始碼。

## 修正問題後重新發佈

1. 修改、通過測試、commit。
2. 執行 `scripts\release.cmd --publish-dir ...`。
3. 通知同事執行新版的 `update.cmd`。

## 退回舊版

舊的發佈資料夾都會保留。請同事解壓縮舊版的 zip，再執行裡面的 `update.cmd`；
設定一樣會保留。

## 注意事項

- 安裝包不含任何權杖或密碼，也不含你本機的 host.json、Skill、Knowledge 或對話。
  同事的模型和整合要在他自己的 Settings 頁設定。
- 安裝包要求同事電腦有 64 位元 Python 3.12，見安裝手冊第 1 節。
- 版本號目前固定是 `0.1.0`，用版本碼（commit）區分各次發佈。
