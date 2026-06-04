from __future__ import annotations
import base64
import hashlib
import hmac
import os
from flask import Flask, request, abort
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from stock_engine import analyze
from line_client import (
    reply_message,
    push_message,
    text_msg,
    main_menu_msg,
    price_menu_msg,
    status_msg,
    flex_report,
    flex_theme_report,
)
from storage import get_user_setting, save_user_setting

load_dotenv()
app = Flask(__name__)

PROCESSED_EVENTS: set[str] = set()
MAX_EVENT_CACHE = 500


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
    parts = (
        text.replace("價格選單📝", " ")
        .replace("價格選單", " ")
        .replace("價格", " ")
        .replace("～", " ")
        .replace("~", " ")
        .replace("-", " ")
        .split()
    )

    nums: list[float] = []
    for p in parts:
        try:
            nums.append(float(p))
        except Exception:
            pass

    if len(nums) >= 2:
        a, b = nums[0], nums[1]
        return min(a, b), max(a, b)

    return None


def parse_mode(text: str) -> int | None:
    t = text.strip().replace(" ", "")

    mode_map = {
        "1": 1,
        "模式1": 1,
        "尚未起漲": 1,
        "尚未起漲💷": 1,
        "1尚未起漲": 1,
        "1尚未起漲💷": 1,

        "2": 2,
        "模式2": 2,
        "題材布局": 2,
        "題材布局💡": 2,
        "2題材布局": 2,
        "2題材布局💡": 2,

        "3": 3,
        "模式3": 3,
        "即將起漲": 3,
        "即將起漲💸": 3,
        "3即將起漲": 3,
        "3即將起漲💸": 3,

        "4": 4,
        "模式4": 4,
        "綜合排行": 4,
        "綜合排行👓": 4,
        "4綜合排行": 4,
        "4綜合排行👓": 4,

        "5": 5,
        "模式5": 5,
        "全部分析": 5,
        "全部分析📋": 5,
        "5全部分析": 5,
        "5全部分析📋": 5,
    }

    return mode_map.get(t)


def build_messages(report) -> list[dict]:
    if report["kind"] == "stocks":
        return [flex_report(report["title"], report["subtitle"], report["rows"])]

    if report["kind"] == "themes":
        return [flex_theme_report(report["title"], report["subtitle"], report["themes"])]

    if report["kind"] == "multi":
        msgs: list[dict] = []
        for r in report["reports"]:
            msgs.extend(build_messages(r))
        return msgs[:5]

    return [text_msg("無法產生報告")]


def run_analysis_messages(mode: int, price_min: float, price_max: float) -> list[dict]:
    top_n = int(os.getenv("TOP_N", "10"))
    report = analyze(mode=mode, price_min=price_min, price_max=price_max, top_n=top_n)
    return build_messages(report)


def mark_processed(event_id: str | None) -> bool:
    if not event_id:
        return True

    if event_id in PROCESSED_EVENTS:
        return False

    PROCESSED_EVENTS.add(event_id)

    if len(PROCESSED_EVENTS) > MAX_EVENT_CACHE:
        for x in list(PROCESSED_EVENTS)[:100]:
            PROCESSED_EVENTS.discard(x)

    return True


@app.get("/")
def index():
    return "Sheng-Stock V6 LINE Bot is running. Use /callback for LINE webhook.", 200


@app.post("/callback")
def callback():
    body = request.get_data()

    if not verify_signature(body, request.headers.get("X-Line-Signature")):
        abort(400)

    payload = request.get_json(force=True)

    for event in payload.get("events", []):
        event_id = event.get("webhookEventId")
        if not mark_processed(event_id):
            continue

        if event.get("type") != "message":
            continue

        if event.get("message", {}).get("type") != "text":
            continue

        reply_token = event.get("replyToken")
        user_id = event.get("source", {}).get("userId") or os.getenv("LINE_TO_ID", "")
        text = event.get("message", {}).get("text", "").strip()
        st = get_user_setting(user_id)

        if text in ("選單", "menu", "Menu", "MENU", "查詢", "開始", "主選單"):
            reply_message(
                reply_token,
                [
                    status_msg(st["mode"], st["price_min"], st["price_max"]),
                    main_menu_msg(),
                ],
            )
            continue

        if text in ("價格選單", "價格選單📝", "價格", "股價", "區間"):
            reply_message(reply_token, [price_menu_msg()])
            continue

        if text.startswith("價格"):
            pr = parse_price(text)

            if not pr:
                reply_message(
                    reply_token,
                    [
                        text_msg("請輸入：價格 100 300\n或點選價格選單。"),
                        price_menu_msg(),
                    ],
                )
                continue

            st = save_user_setting(user_id, price_min=pr[0], price_max=pr[1])
            reply_message(
                reply_token,
                [
                    text_msg(
                        f"✅ 價格區間已設定：{pr[0]:g}~{pr[1]:g} 元\n接著請選擇分析模式。"
                    ),
                    main_menu_msg(),
                ],
            )
            continue

        mode = parse_mode(text)
        if mode:
            st = save_user_setting(user_id, mode=mode)

            try:
                msgs = run_analysis_messages(mode, st["price_min"], st["price_max"])
                reply_message(reply_token, msgs)
            except Exception as e:
                reply_message(
                    reply_token,
                    [text_msg(f"分析失敗：{e}\n請稍後再試，或調整價格區間。")],
                )

            continue

        if text in ("狀態", "設定"):
            reply_message(
                reply_token,
                [
                    status_msg(st["mode"], st["price_min"], st["price_max"]),
                    main_menu_msg(),
                ],
            )
            continue

        reply_message(
            reply_token,
            [text_msg("請輸入「選單」開始，或輸入「價格選單」設定股價區間。")],
        )

    return "OK", 200


def auto_push_job():
    if os.getenv("AUTO_PUSH_ENABLED", "0") != "1":
        return

    to_id = os.getenv("LINE_TO_ID", "").strip()
    if not to_id:
        print("AUTO_PUSH skipped: LINE_TO_ID empty")
        return

    mode = int(os.getenv("DEFAULT_ANALYSIS_MODE", "1"))
    pmin = float(os.getenv("DEFAULT_PRICE_MIN", "10"))
    pmax = float(os.getenv("DEFAULT_PRICE_MAX", "300"))

    try:
        msgs = run_analysis_messages(mode, pmin, pmax)
        push_message(to_id, msgs)
    except Exception as e:
        print("AUTO_PUSH failed", e)


if os.getenv("ENABLE_SCHEDULER", "1") == "1":
    scheduler = BackgroundScheduler(timezone=os.getenv("TZ", "Asia/Taipei"))
    scheduler.add_job(
        auto_push_job,
        CronTrigger(
            hour=int(os.getenv("AUTO_PUSH_HOUR", "18")),
            minute=int(os.getenv("AUTO_PUSH_MINUTE", "0")),
        ),
        id="auto_push_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
