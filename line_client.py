import os
import json
import requests

LINE_API = "https://api.line.me/v2/bot/message"


def _headers():
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN is empty")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def reply_message(reply_token: str, messages: list[dict]):
    url = f"{LINE_API}/reply"
    payload = {"replyToken": reply_token, "messages": messages[:5]}
    r = requests.post(url, headers=_headers(), data=json.dumps(payload), timeout=30)
    if not r.ok:
        print("LINE reply failed", r.status_code, r.text)
    return r


def push_message(to_id: str, messages: list[dict]):
    url = f"{LINE_API}/push"
    payload = {"to": to_id, "messages": messages[:5]}
    r = requests.post(url, headers=_headers(), data=json.dumps(payload), timeout=30)
    if not r.ok:
        print("LINE push failed", r.status_code, r.text)
    return r


def text_msg(text: str) -> dict:
    return {"type": "text", "text": text[:5000]}


def quick_menu_msg() -> dict:
    return {
        "type": "text",
        "text": "請選擇分析模式，或先設定價格區間。",
        "quickReply": {
            "items": [
                {"type": "action", "action": {"type": "message", "label": "10~50", "text": "價格 10 50"}},
                {"type": "action", "action": {"type": "message", "label": "50~100", "text": "價格 50 100"}},
                {"type": "action", "action": {"type": "message", "label": "100~300", "text": "價格 100 300"}},
                {"type": "action", "action": {"type": "message", "label": "300~1000", "text": "價格 300 1000"}},
                {"type": "action", "action": {"type": "message", "label": "尚未起漲", "text": "模式 1"}},
                {"type": "action", "action": {"type": "message", "label": "題材", "text": "模式 2"}},
                {"type": "action", "action": {"type": "message", "label": "即將起漲", "text": "模式 3"}},
                {"type": "action", "action": {"type": "message", "label": "綜合排行", "text": "模式 4"}},
                {"type": "action", "action": {"type": "message", "label": "全部分析", "text": "模式 5"}},
            ]
        },
    }


def flex_report(title: str, subtitle: str, rows: list[dict], footer: str = "公開籌碼資料篩選，不是買賣建議。") -> dict:
    items = []
    for i, row in enumerate(rows[:10], start=1):
        code = str(row.get("code", ""))
        name = str(row.get("name", ""))
        grade = str(row.get("grade", "A 關注"))
        close = row.get("close", "-")
        turnover = row.get("turnover_m", "-")
        inst = row.get("institutional", row.get("net_buy", "-"))
        reason = str(row.get("reason", ""))[:90]
        items.append({
            "type": "box",
            "layout": "vertical",
            "margin": "md",
            "paddingAll": "14px",
            "backgroundColor": "#F8FAFC",
            "cornerRadius": "14px",
            "contents": [
                {"type": "box", "layout": "horizontal", "contents": [
                    {"type": "text", "text": f"{i}. {code} {name}", "weight": "bold", "size": "lg", "color": "#111827", "flex": 3},
                    {"type": "text", "text": grade, "weight": "bold", "size": "sm", "color": "#10B981", "align": "end", "flex": 2},
                ]},
                {"type": "text", "text": f"收盤 {close}｜成交額 {turnover}百萬", "size": "sm", "color": "#4B5563", "wrap": True, "margin": "sm"},
                {"type": "text", "text": f"法人 {inst}張", "size": "sm", "color": "#4B5563", "wrap": True},
                {"type": "text", "text": f"理由：{reason}", "size": "sm", "color": "#6B7280", "wrap": True, "margin": "xs"},
            ],
        })
    if not items:
        items.append({"type": "text", "text": "本次條件沒有篩到股票。", "wrap": True, "color": "#6B7280"})

    return {
        "type": "flex",
        "altText": title,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#111827",
                "paddingAll": "20px",
                "contents": [
                    {"type": "text", "text": title, "weight": "bold", "size": "xl", "color": "#FFFFFF", "wrap": True},
                    {"type": "text", "text": subtitle, "size": "sm", "color": "#D1D5DB", "wrap": True, "margin": "sm"},
                ],
            },
            "body": {"type": "box", "layout": "vertical", "contents": items},
            "footer": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": footer, "size": "xs", "color": "#6B7280", "wrap": True}]},
        },
    }


def flex_theme_report(title: str, subtitle: str, themes: list[dict]) -> dict:
    rows = []
    for i, t in enumerate(themes[:8], 1):
        rows.append({
            "type": "box", "layout": "vertical", "margin": "md", "paddingAll": "14px", "backgroundColor": "#F8FAFC", "cornerRadius": "14px",
            "contents": [
                {"type": "text", "text": f"{i}. {t.get('theme')}", "weight": "bold", "size": "lg", "color": "#111827"},
                {"type": "text", "text": f"近幾日法人 {t.get('recent_net', 0):,}張｜今日 {t.get('today_net', 0):,}張", "size": "sm", "color": "#4B5563", "wrap": True, "margin": "sm"},
                {"type": "text", "text": f"代表：{t.get('leader', '-')}", "size": "sm", "color": "#6B7280", "wrap": True},
            ]
        })
    if not rows:
        rows = [{"type":"text","text":"本次條件沒有篩到題材。","wrap":True}]
    return {"type":"flex","altText":title,"contents":{"type":"bubble","size":"mega","header":{"type":"box","layout":"vertical","backgroundColor":"#7C3AED","paddingAll":"20px","contents":[{"type":"text","text":title,"weight":"bold","size":"xl","color":"#FFFFFF"},{"type":"text","text":subtitle,"size":"sm","color":"#EDE9FE","margin":"sm","wrap":True}]},"body":{"type":"box","layout":"vertical","contents":rows},"footer":{"type":"box","layout":"vertical","contents":[{"type":"text","text":"公開籌碼資料篩選，不是買賣建議。","size":"xs","color":"#6B7280","wrap":True}]}}}
