# AEP Shared Platform Preview：安裝與測試起點

這是 **Shared Platform** 安裝包，不是 Personal Agent + Bridge。一般公司電腦不需安裝
這一包；它應安裝在提供團隊 Registry、Marketplace 與 Bridge API 的共享電腦。

## 安裝

需求：64-bit Windows 10/11 與 64-bit Python 3.12。解壓縮到短路徑，例如
`C:\aep-platform`，然後在可看到 `install.cmd` 的 PowerShell 執行：

```powershell
.\install.cmd -Administrator platform-admin
```

安裝位置：

```text
%LOCALAPPDATA%\AgenticEngineeringPlatform\shared-platform-preview-0.1.0
```

安裝器預設只監聽 `127.0.0.1`，不會立刻暴露到公司網路，也不會建立邀請。

## 驗證與啟動

```powershell
.\verify.cmd
.\start-platform.cmd
```

### Expected result

- `verify.cmd` 顯示 bundle source revision 與 `shared platform configuration: valid`。
- 啟動後終端顯示 Bridge API 與 Member Portal URL。
- 本機可以開啟 Member Portal；停止程序不會刪除 Registry database。

如果顯示 Windows socket `10048` 或 port occupied，代表 `control_port` 或
`member_port` 已有其他程序使用。先確認是否為正在運作的舊 Shared Platform；不要直接
停止不明程序。若不是既有平台，為兩個入口各選一個未使用且不同的 port，更新
`platform.json` 後重啟。

## 讓其他電腦連線前

編輯安裝目錄中的 `platform.json`：

1. 將 `listen_host` 設為這台共享電腦的固定 DNS 名稱或 IP。
2. 設定 `tls_certificate_path` 與 `tls_private_key_path`；非 loopback listener 沒有 TLS
   會被程式拒絕。
3. 確認 `control_port` 與 `member_port` 的防火牆規則只允許預期網路。
4. 在 `invitations` 加入具期限的邀請，再啟動並安全交付產生的 invitation link。

詳細格式與目前 reference-process 限制請看 `README.md`。TLS private key、邀請連結、
Bridge token 與其他 secret 不可提交到 GitHub 或附在測試 evidence。

## Evidence

回報測試時請保留 artifact 名稱、workflow run URL、bundle revision、兩個實際 URL、
Member Portal 畫面，以及 sanitized 的錯誤碼。不得附上 invitation proof 或 token。
