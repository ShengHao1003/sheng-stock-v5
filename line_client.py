from __future__ import annotations
import os
import requests
from typing import Any

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def _headers() -> dict[str, str]:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def text_msg(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text[:5000]}


def reply_message(reply_token: str, messages: list[dict[str, Any]]) -> None:
    if not reply_token:
        return
    payload = {"replyToken": reply_token, "messages": messages[:5]}
    r = requests.post(LINE_REPLY_URL, headers=_headers(), json=payload, timeout=20)
    if r.status_code >= 300:
        print("LINE reply failed", r.status_code, r.text[:500])


def push_message(to: str, messages: list[dict[str, Any]]) -> None:
    if not to:
        print("LINE push skipped: empty to")
        return
    payload = {"to": to, "messages": messages[:5]}
    r = requests.post(LINE_PUSH_URL, headers=_headers(), json=payload, timeout=20)
    if r.status_code >= 300:
        print("LINE push failed", r.status_code, r.text[:500])


def quick_reply_text(title: str, items: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "type": "text",
        "text": title,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {"type": "message", "label": label[:20], "text": text[:300]},
                }
                for label, text in items[:13]
            ]
        },
    }


def main_menu_msg(user_name: str = "聖豪") -> dict[str, Any]:
    return quick_reply_text(
        f"{user_name}，請選擇分析模式 📊",
        [
            ("1 尚未起漲", "模式 1"),
            ("2 題材布局", "模式 2"),
            ("3 即將起漲", "模式 3"),
            ("4 綜合排行", "模式 4"),
            ("5 全部分析", "模式 5"),
            ("設定價格", "價格選單"),
        ],
    )


def price_menu_msg() -> dict[str, Any]:
    return quick_reply_text(
        "💰 請選擇股價篩選區間",
        [
            ("10~50", "價格 10 50"),
            ("50~100", "價格 50 100"),
            ("100~300", "價格 100 300"),
            ("300~1000", "價格 300 1000"),
            ("不限", "價格 0 9999"),
            ("回主選單", "選單"),
        ],
    )


def status_msg(mode: int, pmin: float, pmax: float) -> dict[str, Any]:
    return text_msg(f"目前設定\n模式：{mode_name(mode)}\n價格：{pmin:g}~{pmax:g} 元\n\n輸入「選單」可重新選擇。")


def mode_name(mode: int) -> str:
    return {
        1: "大戶佈局尚未起漲",
        2: "最近大戶佈局題材",
        3: "大戶佈局即將起漲",
        4: "綜合評分排行榜",
        5: "自動全部分析",
    }.get(mode, "未知模式")


def stars(score: float) -> str:
    n = max(1, min(5, int(round(score / 20))))
    return "★" * n + "☆" * (5 - n)


def flex_report(title: str, subtitle: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    contents = []
    for i, r in enumerate(rows[:10], 1):
        code = str(r.get("code", ""))
        name = str(r.get("name", ""))
        close = r.get("close", "-")
        score = float(r.get("score", 0) or 0)
        net = r.get("foreign_net", r.get("total_net", 0))
        reason = str(r.get("reason", ""))[:80]
        contents.append({
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "contents": [
                {"type": "text", "text": f"{i}. {code} {name}  {score:.0f}分", "weight": "bold", "size": "sm", "color": "#111827"},
                {"type": "text", "text": f"收盤 {close}｜法人/外資 {net:+,.0f}張｜{stars(score)}", "size": "xs", "color": "#374151"},
                {"type": "text", "text": reason or "符合籌碼篩選條件", "size": "xs", "color": "#6B7280", "wrap": True},
            ],
            "paddingBottom": "md",
        })
    if not contents:
        contents.append({"type": "text", "text": "本次沒有符合條件的股票。", "wrap": True, "size": "sm"})
    return {
        "type": "flex",
        "altText": title,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {"type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg", "color": "#FFFFFF"},
                {"type": "text", "text": subtitle, "size": "xs", "color": "#E5E7EB", "wrap": True},
            ], "backgroundColor": "#111827", "paddingAll": "16px"},
            "body": {"type": "box", "layout": "vertical", "contents": contents, "spacing": "sm"},
            "footer": {"type": "box", "layout": "vertical", "contents": [
                {"type": "text", "text": "僅供研究，不構成投資建議。輸入「選單」可再次查詢。", "size": "xxs", "color": "#9CA3AF", "wrap": True}
            ]},
        },
    }


def flex_theme_report(title: str, subtitle: str, themes: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for i, t in enumerate(themes[:10], 1):
        names = "、".join(t.get("top_names", [])[:4])
        rows.append({
            "type": "box", "layout": "vertical", "spacing": "xs", "paddingBottom": "md",
            "contents": [
                {"type": "text", "text": f"{i}. {t.get('theme','')}  {t.get('score',0):.0f}分", "weight": "bold", "size": "sm", "color": "#7C2D12"},
                {"type": "text", "text": f"法人買超 {t.get('total_net',0):+,.0f}張｜代表：{names}", "size": "xs", "color": "#374151", "wrap": True},
            ]
        })
    if not rows:
        rows.append({"type":"text","text":"本次沒有符合條件的題材。","size":"sm"})
    return {
        "type": "flex", "altText": title,
        "contents": {
            "type":"bubble", "size":"mega",
            "header":{"type":"box","layout":"vertical","backgroundColor":"#F97316","paddingAll":"16px","contents":[
                {"type":"text","text":title,"weight":"bold","size":"lg","color":"#FFFFFF"},
                {"type":"text","text":subtitle,"size":"xs","color":"#FFEDD5","wrap":True},
            ]},
            "body":{"type":"box","layout":"vertical","contents":rows,"spacing":"sm"},
            "footer":{"type":"box","layout":"vertical","contents":[{"type":"text","text":"題材統計依內建族群清單彙總，僅供研究。","size":"xxs","color":"#9CA3AF","wrap":True}]}
        }
    }
