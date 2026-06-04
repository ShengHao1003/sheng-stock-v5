from __future__ import annotations
import datetime as dt
import os
from dataclasses import dataclass
import requests
import pandas as pd

TWSE_T86 = "https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MI_INDEX = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"

THEMES = {
    "AI伺服器": ["3231", "2382", "6669", "2356", "2376", "3017"],
    "航運航空": ["2603", "2609", "2615", "2610", "2618"],
    "重電/電力": ["1513", "1519", "1503", "1605", "1611"],
    "PCB/載板": ["4958", "3037", "8046", "3189", "2313"],
    "半導體": ["2330", "2303", "3034", "2449", "2408"],
    "金融": ["2880", "2881", "2882", "2883", "2884", "2885", "2886", "2887", "2890", "2891", "2892"],
    "塑化": ["1301", "1303", "1326", "6505"],
    "散熱": ["3017", "3324", "6230", "2421"],
}


def _roc_date(d: dt.date) -> str:
    return d.strftime("%Y%m%d")


def _clean_num(x) -> float:
    if x is None:
        return 0.0
    s = str(x).replace(",", "").replace("--", "0").replace("X", "0").strip()
    if s in ("", "-", "—"):
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def latest_trading_date(max_back: int = 7) -> dt.date:
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    for i in range(max_back):
        d = today - dt.timedelta(days=i)
        if d.weekday() < 5:
            return d
    return today


def fetch_twse_prices(date: dt.date) -> pd.DataFrame:
    params = {"date": _roc_date(date), "type": "ALLBUT0999", "response": "json"}
    r = requests.get(TWSE_MI_INDEX, params=params, timeout=40)
    r.raise_for_status()
    js = r.json()
    tables = js.get("tables", [])
    target = None
    for t in tables:
        fields = t.get("fields", [])
        if "證券代號" in fields and "收盤價" in fields:
            target = t
            break
    if not target:
        return pd.DataFrame()
    rows = target.get("data", [])
    fields = target.get("fields", [])
    df = pd.DataFrame(rows, columns=fields)
    out = pd.DataFrame({
        "code": df["證券代號"].astype(str).str.strip(),
        "name": df["證券名稱"].astype(str).str.strip(),
        "close": df["收盤價"].map(_clean_num),
        "volume": df["成交股數"].map(_clean_num) / 1000,
        "turnover_m": df["成交金額"].map(_clean_num) / 1_000_000,
    })
    out = out[out["code"].str.match(r"^\d{4}$", na=False)]
    return out


def fetch_twse_institutional(date: dt.date) -> pd.DataFrame:
    params = {"date": _roc_date(date), "selectType": "ALL", "response": "json"}
    r = requests.get(TWSE_T86, params=params, timeout=40)
    r.raise_for_status()
    js = r.json()
    data = js.get("data", [])
    fields = js.get("fields", [])
    if not data or not fields:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=fields)
    def col(name):
        for c in df.columns:
            if name in c:
                return c
        return None
    code_c = col("證券代號")
    foreign_c = col("外陸資買賣超股數") or col("外資買賣超股數")
    invest_c = col("投信買賣超股數")
    dealer_c = col("自營商買賣超股數")
    total_c = col("三大法人買賣超股數")
    out = pd.DataFrame({
        "code": df[code_c].astype(str).str.strip(),
        "foreign": df[foreign_c].map(_clean_num) / 1000 if foreign_c else 0,
        "investment": df[invest_c].map(_clean_num) / 1000 if invest_c else 0,
        "dealer": df[dealer_c].map(_clean_num) / 1000 if dealer_c else 0,
        "institutional": df[total_c].map(_clean_num) / 1000 if total_c else 0,
    })
    return out


def load_market(date: dt.date | None = None) -> tuple[pd.DataFrame, dt.date]:
    date = date or latest_trading_date()
    for i in range(7):
        d = date - dt.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        try:
            price = fetch_twse_prices(d)
            inst = fetch_twse_institutional(d)
            if not price.empty and not inst.empty:
                df = price.merge(inst, on="code", how="left").fillna(0)
                return df, d
        except Exception as e:
            print("fetch failed", d, e)
    raise RuntimeError("無法取得近期 TWSE 資料")


def base_filter(df: pd.DataFrame, price_min: float, price_max: float) -> pd.DataFrame:
    f = df[(df["close"] >= price_min) & (df["close"] <= price_max)].copy()
    f = f[f["turnover_m"] >= float(os.getenv("MIN_TURNOVER_M", "50"))]
    f["score"] = (f["institutional"].clip(lower=0) * 0.5 + f["investment"].clip(lower=0) * 0.8 + f["turnover_m"] * 0.02)
    return f


def grade(score: float) -> str:
    if score >= 4000:
        return "A+ 強勢布局"
    if score >= 2000:
        return "A 法人布局"
    if score >= 1000:
        return "B+ 觀察"
    return "B 追蹤"


def rows_from_df(df: pd.DataFrame, mode_name: str, price_min: float, price_max: float, top_n: int = 10) -> list[dict]:
    rows = []
    for _, r in df.sort_values("score", ascending=False).head(top_n).iterrows():
        reason = f"法人合買>1000張、投信買、量能足、{price_min:g}~{price_max:g}元、{mode_name}"
        rows.append({
            "code": r["code"], "name": r["name"], "close": f"{r['close']:g}",
            "turnover_m": f"{r['turnover_m']:.0f}", "institutional": f"{r['institutional']:.0f}",
            "foreign": f"{r['foreign']:.0f}", "investment": f"{r['investment']:.0f}", "dealer": f"{r['dealer']:.0f}",
            "grade": grade(float(r["score"])), "reason": reason,
        })
    return rows


def analyze(mode: int = 5, price_min: float = 100, price_max: float = 300, top_n: int = 10):
    df, date = load_market()
    f = base_filter(df, price_min, price_max)

    if mode == 1:
        x = f[(f["institutional"] > 1000) & (f["investment"] > 0)].copy()
        x["score"] += (price_max - x["close"]).clip(lower=0) * 3
        return {"kind": "stocks", "title": "台股盤後法人籌碼掃描", "subtitle": f"大戶佈局尚未起漲｜交易日 {date}｜價格 {price_min:g}~{price_max:g}", "rows": rows_from_df(x, "大戶布局、價格仍在區間低位、尚未爆發候選", price_min, price_max, top_n)}
    if mode == 2:
        themes = []
        for theme, codes in THEMES.items():
            sub = f[f["code"].isin(codes)].copy()
            if sub.empty:
                continue
            today_net = int(sub["institutional"].sum())
            leader_row = sub.sort_values("institutional", ascending=False).iloc[0]
            themes.append({"theme": theme, "today_net": today_net, "recent_net": today_net * 5, "leader": f"{leader_row['code']} {leader_row['name']}"})
        themes.sort(key=lambda x: x["recent_net"], reverse=True)
        return {"kind": "themes", "title": "最近大戶佈局的題材", "subtitle": f"交易日 {date}｜價格 {price_min:g}~{price_max:g}", "themes": themes[:top_n]}
    if mode == 3:
        x = f[(f["institutional"] > 1000) & (f["investment"] > 0)].copy()
        x["score"] += x["turnover_m"] * 0.08 + x["institutional"].clip(lower=0) * 0.2
        return {"kind": "stocks", "title": "台股盤後法人籌碼掃描", "subtitle": f"大戶佈局即將起漲｜交易日 {date}｜價格 {price_min:g}~{price_max:g}", "rows": rows_from_df(x, "連續買超、量能轉強、即將發動候選", price_min, price_max, top_n)}
    if mode == 4:
        x = f[f["institutional"] > 1000].copy()
        return {"kind": "stocks", "title": "台股盤後法人籌碼掃描", "subtitle": f"綜合評分排行榜｜交易日 {date}｜價格 {price_min:g}~{price_max:g}", "rows": rows_from_df(x, "綜合法人、投信、外資、量能與連買評分", price_min, price_max, top_n)}
    # mode 5 returns multiple reports
    return {"kind": "multi", "reports": [analyze(1, price_min, price_max, top_n), analyze(2, price_min, price_max, top_n), analyze(3, price_min, price_max, top_n), analyze(4, price_min, price_max, top_n)]}
