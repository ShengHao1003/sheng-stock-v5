# Sheng-Stock V5 Cloud LINE Bot

這版是雲端部署版：電腦關機後，LINE Bot 仍可運作。

## 功能

- LINE 輸入「選單」開啟互動選單
- 用 LINE 選價格區間與分析模式
- 彩色 Flex Message 回傳分析結果
- 支援每日自動推播
- 不需要 FinMind Token
- 直接抓 TWSE / TPEx 公開資料

## 主要檔案

- `app.py`：LINE Webhook 伺服器
- `stock_engine.py`：股票資料與分析邏輯
- `line_client.py`：LINE Push / Reply
- `requirements.txt`：Python 套件
- `render.yaml`：Render 部署設定
- `.env.example`：本機測試設定範例

## Render 部署流程

1. 建立 GitHub Repository
2. 上傳整包檔案
3. 到 Render 建立 Web Service
4. Connect GitHub Repository
5. Build Command：

```bash
pip install -r requirements.txt
```

6. Start Command：

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

7. Render Environment Variables 設定：

```env
LINE_CHANNEL_ACCESS_TOKEN=你的LINE token
LINE_CHANNEL_SECRET=你的Channel secret
LINE_TO_ID=你的U開頭User ID
TZ=Asia/Taipei
AUTO_PUSH_ENABLED=1
AUTO_PUSH_HOUR=18
AUTO_PUSH_MINUTE=0
DEFAULT_PRICE_MIN=100
DEFAULT_PRICE_MAX=300
DEFAULT_ANALYSIS_MODE=5
```

8. Render 會給你網址，例如：

```text
https://sheng-stock-line-bot.onrender.com
```

9. LINE Developers Webhook URL 填：

```text
https://sheng-stock-line-bot.onrender.com/callback
```

10. Use webhook 開啟 Enabled，按 Verify。

## LINE 指令

- `選單`：開啟互動選單
- `查詢`：使用預設條件查詢
- `全部`：跑全部分析
- `價格 100 300`：設定價格區間
- `模式 1`：大戶佈局尚未起漲
- `模式 2`：最近大戶佈局題材
- `模式 3`：大戶佈局即將起漲
- `模式 4`：綜合評分排行榜
- `模式 5`：自動全部分析

## 注意

這是公開籌碼資料分析，不是買賣建議。主力/大戶僅用法人與量價代理估算。
