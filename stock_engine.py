from __future__ import annotations
import datetime as dt
import os
from typing import Any
import numpy as np
import pandas as pd
import requests

TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))

THEMES: dict[str, list[str]] = {
    "AI伺服器": ["2382", "3231", "6669", "2356", "2357", "2317", "2376", "3017"],
    "AI PC/NB": ["2356", "2357", "2324", "2382", "3231", "2376", "4938"],
    "PCB/ABF": ["3037", "3189", "4958", "8046", "2368", "6274", "6153", "2313"],
    "玻璃基板": ["2409", "3481", "6182", "8046", "4958", "3017"],
    "CoWoS/先進封裝": ["2330", "2449", "3260", "3711", "3450", "6274"],
    "機器人": ["2049", "3019", "2464", "1590", "2359", "2371", "4572"],
    "散熱": ["3017", "3324", "6230", "3653", "2421", "8996"],
    "CPO/光通訊": ["3081", "3163", "3450", "4908", "4979", "6530"],
    "重電": ["1503", "1513", "1519", "1605", "1609", "1618", "2371"],
    "軍工/航太": ["2634", "4572", "8222", "8033", "2645", "6753"],
    "低軌衛星": ["2317", "2409", "3596", "3491", "6285", "4906"],
    "BBU/儲能": ["1519", "1609", "2308", "3324", "3211", "6121"],
    "航運": ["2603", "2609", "2610", "2618", "2605", "2615"],
    "金融": ["2880", "2881", "2882", "2883", "2884", "2885", "2886", "2887", "2888", "2890", "2891", "2892"],
}


def _dates(back: int = 10):
    today = dt.date.today()
    for i in range(back):
        yield today - dt.timedelta(days=i)


def _clean_num(x: Any) -> float:
    if pd.isna(x):
        return np.nan
    s = str(x).replace(",", "").replace("--", "").replace("X", "").strip()
    if s in ("", "-", "+"):
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def _fetch_twse_price(date: dt.date) -> pd.DataFrame:
    url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
    params = {"date": date.strftime("%Y%m%d"), "type": "ALLBUT0999", "response": "json"}
    js = requests.get(url, params=params, timeout=TIMEOUT).json()
    tables = js.get("tables", [])
    rows = []
    for t in tables:
        fields = t.get("fields", [])
        data = t.get("data", [])
        if "證券代號" in fields and "收盤價" in fields:
            rows = data
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=fields)
    out = pd.DataFrame({
        "code": df["證券代號"].astype(str).str.strip(),
        "name": df["證券名稱"].astype(str).str.strip(),
        "close": df["收盤價"].map(_clean_num),
        "volume": df["成交股數"].map(_clean_num) / 1000,
        "turnover_m": df["成交金額"].map(_clean_num) / 1_000_000,
        "date": date.isoformat(),
        "market": "上市",
    })
    return out.dropna(subset=["close"])


def _fetch_twse_inst(date: dt.date) -> pd.DataFrame:
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"
    params = {"date": date.strftime("%Y%m%d"), "selectType": "ALL", "response": "json"}
    js = requests.get(url, params=params, timeout=TIMEOUT).json()
    data = js.get("data", [])
    fields = js.get("fields", [])
    if not data or not fields:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=fields)
    def col_contains(*ks):
        for c in df.columns:
            if all(k in c for k in ks):
                return c
        return None
    code_col = col_contains("證券代號") or df.columns[0]
    foreign_col = col_contains("外資", "買賣超")
    trust_col = col_contains("投信", "買賣超")
    dealer_col = col_contains("自營商", "買賣超")
    total_col = col_contains("三大法人", "買賣超")
    out = pd.DataFrame({"code": df[code_col].astype(str).str.strip()})
    out["foreign_net"] = df[foreign_col].map(_clean_num) / 1000 if foreign_col else 0
    out["trust_net"] = df[trust_col].map(_clean_num) / 1000 if trust_col else 0
    out["dealer_net"] = df[dealer_col].map(_clean_num) / 1000 if dealer_col else 0
    if total_col:
        out["total_net"] = df[total_col].map(_clean_num) / 1000
    else:
        out["total_net"] = out["foreign_net"] + out["trust_net"] + out["dealer_net"]
    return out


def _fetch_tpex_price(date: dt.date) -> pd.DataFrame:
    # 櫃買資料格式偶爾調整；失敗時回空表，不影響上市分析
    url = "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc"
    params = {"date": date.strftime("%Y/%m/%d"), "type": "EW", "response": "json"}
    try:
        js = requests.get(url, params=params, timeout=TIMEOUT).json()
    except Exception:
        return pd.DataFrame()
    data = js.get("tables", [{}])[0].get("data", []) if js.get("tables") else js.get("data", [])
    fields = js.get("tables", [{}])[0].get("fields", []) if js.get("tables") else js.get("fields", [])
    if not data or not fields:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=fields[:len(data[0])])
    def find(k):
        return next((c for c in df.columns if k in c), None)
    code_col = find("代號") or df.columns[0]
    name_col = find("名稱") or df.columns[1]
    close_col = find("收盤") or find("最後")
    vol_col = find("成交股數") or find("成交量")
    amt_col = find("成交金額")
    if not close_col:
        return pd.DataFrame()
    out = pd.DataFrame({
        "code": df[code_col].astype(str).str.strip(),
        "name": df[name_col].astype(str).str.strip(),
        "close": df[close_col].map(_clean_num),
        "volume": df[vol_col].map(_clean_num) / 1000 if vol_col else 0,
        "turnover_m": df[amt_col].map(_clean_num) / 1_000_000 if amt_col else 0,
        "date": date.isoformat(),
        "market": "上櫃",
    })
    return out.dropna(subset=["close"])


def get_market_snapshot() -> pd.DataFrame:
    last_err = None
    for d in _dates(12):
        try:
            price = _fetch_twse_price(d)
            inst = _fetch_twse_inst(d)
            if price.empty or inst.empty:
                continue
            df = price.merge(inst, on="code", how="left")
            # TPEx price only as price extension; institutional fallback as zero if not available
            tpex = _fetch_tpex_price(d)
            if not tpex.empty:
                for c in ["foreign_net", "trust_net", "dealer_net", "total_net"]:
                    tpex[c] = 0.0
                df = pd.concat([df, tpex], ignore_index=True)
            for c in ["foreign_net", "trust_net", "dealer_net", "total_net", "volume", "turnover_m"]:
                df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)
            return df
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"無法取得最近交易日資料：{last_err}")


def _add_scores(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["price_power"] = np.where(d["close"] <= 50, 20, np.where(d["close"] <= 100, 15, np.where(d["close"] <= 300, 10, 5)))
    d["inst_power"] = np.clip(d["total_net"] / 3000 * 40, 0, 40)
    d["trust_power"] = np.clip(d["trust_net"] / 1000 * 25, 0, 25)
    d["volume_power"] = np.clip(d["turnover_m"] / 500 * 15, 0, 15)
    d["score"] = d["inst_power"] + d["trust_power"] + d["volume_power"] + d["price_power"]
    d["reason"] = d.apply(lambda r: f"三大法人 {r.total_net:+.0f}張、投信 {r.trust_net:+.0f}張、成交額 {r.turnover_m:.0f}百萬", axis=1)
    return d


def _filter_base(price_min: float, price_max: float) -> pd.DataFrame:
    df = get_market_snapshot()
    df = df[(df["close"] >= price_min) & (df["close"] <= price_max)].copy()
    return _add_scores(df)


def _theme_strength_map(df: pd.DataFrame) -> dict[str, float]:
    """依目前快照估算題材熱度；公開資料限制下，以法人買超與成交金額做代理。"""
    strength: dict[str, float] = {}
    for theme, codes in THEMES.items():
        g = df[df["code"].isin(codes)]
        if g.empty:
            continue
        total_net = float(g["total_net"].sum())
        turnover = float(g["turnover_m"].sum())
        strength[theme] = max(0.0, min(100.0, total_net / 5000 * 60 + turnover / 1000 * 40))
    return strength


def _add_theme_columns(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    strength = _theme_strength_map(d)
    def pick_theme(code: str) -> tuple[str, float]:
        hits = [(theme, strength.get(theme, 0.0)) for theme, codes in THEMES.items() if code in codes]
        if not hits:
            return "一般", 0.0
        return max(hits, key=lambda x: x[1])
    picked = d["code"].map(pick_theme)
    d["theme"] = [x[0] for x in picked]
    d["theme_power"] = [x[1] for x in picked]
    return d


def _system_recommend(df: pd.DataFrame) -> pd.DataFrame:
    """系統推薦：法人、投信、量能、題材、價格位置綜合評分。"""
    d = _add_theme_columns(df)
    d["system_score"] = (
        np.clip(d["total_net"] / 3000 * 30, 0, 30) +
        np.clip(d["trust_net"] / 1000 * 15, 0, 15) +
        np.clip(d["volume"] / 20000 * 15, 0, 15) +
        np.clip(d["turnover_m"] / 800 * 10, 0, 10) +
        np.clip(d["theme_power"] / 100 * 10, 0, 10) +
        np.where((d["total_net"] > 0) & (d["foreign_net"] > 0), 10, 0) +
        np.where(d["close"] <= 300, 10, 5)
    )
    d["score"] = np.clip(d["system_score"], 0, 100)
    d["reason"] = d.apply(
        lambda r: f"系統推薦｜題材 {r.theme}｜三大法人 {r.total_net:+.0f}張、投信 {r.trust_net:+.0f}張、成交額 {r.turnover_m:.0f}百萬",
        axis=1,
    )
    return d


def _stock_report(title: str, subtitle: str, rows: pd.DataFrame, top_n: int) -> dict[str, Any]:
    cols = ["code", "name", "close", "market", "foreign_net", "trust_net", "dealer_net", "total_net", "turnover_m", "score", "reason"]
    data = rows.sort_values("score", ascending=False).head(top_n)[cols].to_dict("records") if not rows.empty else []
    return {"kind": "stocks", "title": title, "subtitle": subtitle, "rows": data}


def analyze(mode: int, price_min: float, price_max: float, top_n: int = 10) -> dict[str, Any]:
    df = _filter_base(price_min, price_max)
    sub = f"價格 {price_min:g}~{price_max:g} 元｜資料來源：TWSE/TPEx 公開資料"

    if mode == 1:
        # 大戶佈局尚未起漲：法人進場、有基本成交額，偏向低價或尚未過熱的標的。
        rows = df[(df["total_net"] > 500) & (df["turnover_m"] > 50)].copy()
        rows["score"] += np.where(rows["close"] <= 50, 10, np.where(rows["close"] <= 100, 5, 0))
        rows["reason"] = rows.apply(lambda r: f"尚未起漲代理｜三大法人 {r.total_net:+.0f}張、投信 {r.trust_net:+.0f}張、成交額 {r.turnover_m:.0f}百萬", axis=1)
        return _stock_report("🟢 大戶佈局尚未起漲", sub, rows, top_n)

    if mode == 2:
        themes = []
        for theme, codes in THEMES.items():
            g = df[df["code"].isin(codes)].copy()
            if g.empty:
                continue
            total_net = float(g["total_net"].sum())
            turnover = float(g["turnover_m"].sum())
            score = max(0, min(100, total_net / 5000 * 60 + turnover / 1000 * 40))
            top = g.sort_values("score", ascending=False).head(4)
            themes.append({
                "theme": theme,
                "score": score,
                "total_net": total_net,
                "top_names": [f"{r.code} {r.name}" for r in top.itertuples()],
            })
        themes = sorted(themes, key=lambda x: x["score"], reverse=True)[:top_n]
        return {"kind": "themes", "title": "🔥 最近大戶佈局題材", "subtitle": sub, "themes": themes}

    if mode == 3:
        # 即將起漲：法人、投信、成交金額同步強，偏向已開始發動的候選股。
        rows = df[(df["total_net"] > 1000) & (df["trust_net"] > 100) & (df["turnover_m"] > 100)].copy()
        rows["score"] += np.clip(rows["total_net"] / 2000 * 10, 0, 10)
        rows["reason"] = rows.apply(lambda r: f"即將起漲代理｜三大法人 {r.total_net:+.0f}張、投信 {r.trust_net:+.0f}張、成交額 {r.turnover_m:.0f}百萬", axis=1)
        return _stock_report("🚀 大戶佈局即將起漲", sub, rows, top_n)

    if mode == 4:
        return _stock_report("🏆 綜合評分排行榜", sub, df[df["turnover_m"] > 30], top_n)

    if mode == 5:
        # LINE 一次最多5則，全部分析保留四張核心報告。
        return {"kind": "multi", "reports": [
            analyze(1, price_min, price_max, top_n),
            analyze(2, price_min, price_max, top_n),
            analyze(3, price_min, price_max, top_n),
            analyze(9, price_min, price_max, top_n),
        ]}

    if mode == 6:
        # 公開免費資料目前是單日快照；這裡以法人/外資/投信同步買超作為連買排行代理。
        rows = df[(df["total_net"] > 0) & (df["foreign_net"] > 0)].copy()
        rows["score"] = np.clip(rows["total_net"] / 2500 * 55, 0, 55) + np.clip(rows["foreign_net"] / 2000 * 25, 0, 25) + np.clip(rows["trust_net"] / 800 * 20, 0, 20)
        rows["reason"] = rows.apply(lambda r: f"法人連買代理｜外資 {r.foreign_net:+.0f}張、投信 {r.trust_net:+.0f}張、三大法人 {r.total_net:+.0f}張", axis=1)
        return _stock_report("📈 法人連買排行", sub, rows, top_n)

    if mode == 7:
        # 主力佈局代理：法人買超 + 投信買超 + 有成交金額，但避免只看大量金融股。
        rows = df[(df["total_net"] > 700) & (df["turnover_m"] > 80)].copy()
        rows["score"] = (
            np.clip(rows["total_net"] / 3000 * 45, 0, 45) +
            np.clip(rows["trust_net"] / 1000 * 25, 0, 25) +
            np.clip(rows["turnover_m"] / 700 * 20, 0, 20) +
            np.where(rows["close"] <= 300, 10, 5)
        )
        rows["reason"] = rows.apply(lambda r: f"主力佈局代理｜三大法人 {r.total_net:+.0f}張、投信 {r.trust_net:+.0f}張、成交額 {r.turnover_m:.0f}百萬", axis=1)
        return _stock_report("🧲 主力佈局排行", sub, rows, top_n)

    if mode == 8:
        themes = []
        for theme, codes in THEMES.items():
            g = df[df["code"].isin(codes)].copy()
            if g.empty:
                continue
            buy_count = int((g["total_net"] > 0).sum())
            total_net = float(g["total_net"].sum())
            turnover = float(g["turnover_m"].sum())
            score = max(0, min(100, buy_count / max(len(codes), 1) * 35 + total_net / 5000 * 40 + turnover / 1200 * 25))
            top = g.sort_values("score", ascending=False).head(4)
            themes.append({
                "theme": theme,
                "score": score,
                "total_net": total_net,
                "top_names": [f"{r.code} {r.name}" for r in top.itertuples()],
            })
        themes = sorted(themes, key=lambda x: x["score"], reverse=True)[:top_n]
        return {"kind": "themes", "title": "🔄 題材輪動排行", "subtitle": sub, "themes": themes}

    if mode == 9:
        rows = _system_recommend(df)
        rows = rows[(rows["total_net"] > 500) & (rows["turnover_m"] > 50)].copy()
        return _stock_report("🤖 系統推薦", sub, rows, top_n)

    return _stock_report("未知模式", sub, pd.DataFrame(), top_n)
