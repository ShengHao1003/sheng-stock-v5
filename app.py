from __future__ import annotations
import os
import hmac
import base64
import hashlib
from flask import Flask, request, abort
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from stock_engine import analyze
from line_client import reply_message, push_message, text_msg, quick_menu_msg, flex_report, flex_theme_report

load_dotenv()
app = Flask(__name__)

USER_STATE: dict[str, dict] = {}


def verify_signature(body: bytes, signature: str | None) -> bool:
    secret = os.getenv("LINE_CHANNEL_SECRET", "").strip()
    if not secret:
        return True
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def parse_price(text: str):
    parts = text.replace("～", " ").replace("~", " ").replace("-", " ").split()
    nums = []
    for p in parts:
        try:
            nums.append(float(p))
        except Exception:
            pass
    if len(nums) >= 2:
        return nums[0], nums[1]
    return None


def get_state(user_id: str) -> dict:
    st = USER_STATE.setdefault(user_id, {})
    st.setdefault("price_min", float(os.getenv("DEFAULT_PRICE_MIN", "100")))
    st.setdefault("price_max", float(os.getenv("DEFAULT_PRICE_MAX", "300")))
    st.setdefault("mode", int(os.getenv("DEFAULT_ANALYSIS_MODE", "5")))
    return st


def build_messages(report) -> list[dict]:
    if report["kind"] == "stocks":
        return [flex_report(report["title"], report["subtitle"], report["rows"])]
    if report["kind"] == "themes":
        return [flex_theme_report(report["title"], report["subtitle"], report["themes"])]
    if report["kind"] == "multi":
        msgs = []
        for r in report["reports"]:
            msgs.extend(build_messages(r))
        return msgs[:5]
    return [text_msg("無法產生報告")]


def run_analysis_messages(mode: int, price_min: float, price_max: float):
    top_n = int(os.getenv("TOP_N", "10"))
    report = analyze(mode=mode, price_min=price_min, price_max=price_max, top_n=top_n)
    return build_messages(report)


@app.get("/")
def index():
    return "Sheng-Stock V5 LINE Bot is running. Use /callback for LINE webhook.", 200


@app.post("/callback")
def callback():
    body = request.get_data()
    if not verify_signature(body, request.headers.get("X-Line-Signature")):
        abort(400)
    payload = request.get_json(force=True)
    for event in payload.get("events", []):
        if event.get("type") != "message" or event.get("message", {}).get("type") != "text":
            continue
        reply_token = event.get("replyToken")
        user_id = event.get("source", {}).get("userId") or os.getenv("LINE_TO_ID", "")
        text = event.get("message", {}).get("text", "").strip()
        st = get_state(user_id)

        if text in ("選單", "menu", "Menu", "查詢", "開始"):
            reply_message(reply_token, [quick_menu_msg()])
            continue

        if text.startswith("價格"):
            pr = parse_price(text)
            if not pr:
                reply_message(reply_token, [text_msg("請輸入：價格 100 300")])
                continue
            st["price_min"], st["price_max"] = pr
            reply_message(reply_token, [text_msg(f"價格區間已設定：{pr[0]:g}~{pr[1]:g} 元\n接著請輸入：模式 1～5"), quick_menu_msg()])
            continue

        if text.startswith("模式"):
            try:
                mode = int(text.split()[-1])
                if mode not in (1, 2, 3, 4, 5):
                    raise ValueError
            except Exception:
                reply_message(reply_token, [text_msg("請輸入：模式 1、模式 2、模式 3、模式 4 或 模式 5")])
                continue
            st["mode"] = mode
            reply_message(reply_token, [text_msg("收到，開始分析，請稍候。")])
            msgs = run_analysis_messages(mode, st["price_min"], st["price_max"])
            push_message(user_id, msgs)
            continue

        if text in ("1", "2", "3", "4", "5"):
            mode = int(text)
            st["mode"] = mode
            reply_message(reply_token, [text_msg("收到，開始分析，請稍候。")])
            msgs = run_analysis_messages(mode, st["price_min"], st["price_max"])
            push_message(user_id, msgs)
            continue

        reply_message(reply_token, [text_msg("請輸入「選單」開始。")])
    return "OK", 200


def auto_push_job():
    if os.getenv("AUTO_PUSH_ENABLED", "0") != "1":
        return
    to_id = os.getenv("LINE_TO_ID", "").strip()
    if not to_id:
        print("AUTO_PUSH skipped: LINE_TO_ID empty")
        return
    mode = int(os.getenv("DEFAULT_ANALYSIS_MODE", "5"))
    pmin = float(os.getenv("DEFAULT_PRICE_MIN", "100"))
    pmax = float(os.getenv("DEFAULT_PRICE_MAX", "300"))
    try:
        msgs = run_analysis_messages(mode, pmin, pmax)
        push_message(to_id, msgs)
    except Exception as e:
        print("AUTO_PUSH failed", e)


if os.getenv("ENABLE_SCHEDULER", "1") == "1":
    scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Asia/Taipei"))
    scheduler.add_job(auto_push_job, CronTrigger(hour=int(os.getenv("AUTO_PUSH_HOUR", "18")), minute=int(os.getenv("AUTO_PUSH_MINUTE", "0"))))
    scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
