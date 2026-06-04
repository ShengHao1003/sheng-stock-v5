# Sheng-Stock V6 Cloud Render

這是 LINE 雲端互動版股票籌碼分析機器人。

## V6 修正重點

1. 使用者在 LINE 端選擇條件，不需要開 Python 互動輸入。
2. 先選價格區間，再選分析模式。
3. 分析結果改用 `reply_message` 回覆，不再同時 `push_message`，避免黑色籌碼掃描或 Flex 報告重複推播。
4. 新增 SQLite 儲存使用者設定，Render 重啟後仍可保留價格區間與模式。
5. 加入 `webhookEventId` 去重，降低 LINE retry 造成重複回覆的機率。
6. 自動推播預設關閉：`AUTO_PUSH_ENABLED=0`。

## LINE 使用方式

在 LINE 傳：

```text
選單
```

可選：

```text
1. 大戶佈局尚未起漲
2. 最近大戶佈局題材
3. 大戶佈局即將起漲
4. 綜合評分排行榜
5. 自動全部分析
```

設定價格：

```text
價格選單
```

或直接輸入：

```text
價格 100 300
```

## 本機測試

```powershell
py -m pip install -r requirements.txt
copy .env.example .env
py app.py
```

Webhook 本機測試仍需要 Cloudflare Tunnel 或 ngrok：

```powershell
cloudflared tunnel --url http://localhost:5000
```

LINE Developers Webhook URL：

```text
https://你的網址.trycloudflare.com/callback
```

## Render 部署

1. 建立 GitHub Repository。
2. 上傳本資料夾所有檔案。
3. Render → New → Web Service。
4. 選擇 GitHub Repo。
5. Build Command：

```bash
pip install -r requirements.txt
```

6. Start Command：

```bash
gunicorn app:app --workers 1 --threads 4 --timeout 180
```

## Render 環境變數

必要：

```env
LINE_CHANNEL_ACCESS_TOKEN=你的LINE_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET=你的LINE_CHANNEL_SECRET
LINE_TO_ID=你的U開頭UserID
TZ=Asia/Taipei
```

建議：

```env
TOP_N=10
DEFAULT_PRICE_MIN=10
DEFAULT_PRICE_MAX=300
DEFAULT_ANALYSIS_MODE=1
AUTO_PUSH_ENABLED=0
ENABLE_SCHEDULER=1
AUTO_PUSH_HOUR=18
AUTO_PUSH_MINUTE=0
REQUEST_TIMEOUT=20
```

## LINE Developers 設定

Render 部署成功後會得到網址，例如：

```text
https://sheng-stock-v6.onrender.com
```

Webhook URL 填：

```text
https://sheng-stock-v6.onrender.com/callback
```

然後：

1. 按 Update
2. 按 Verify
3. Use webhook = Enabled

## 注意

- 本工具使用 TWSE/TPEx 公開資料。
- 「大戶」是用法人買超、投信買超、成交金額與題材聚合做籌碼代理判斷，並非內線資訊。
- 分析結果僅供研究，不構成投資建議。
