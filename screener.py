from __future__ import annotations

import argparse
import html
from io import StringIO
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup

from config import CONFIG


OUTPUT_COLUMNS = [
    "candidate_level",
    "candidate_score",
    "股票代號",
    "股票名稱",
    "市場",
    "收盤價",
    "MA20",
    "是否站上 MA20",
    "K 值",
    "D 值",
    "RSI",
    "Volume_MA5",
    "Volume_MA20",
    "Volume_MA40",
    "放量倍數",
    "MACD_DIF",
    "MACD_Signal",
    "MACD_Histogram",
    "MACD_Histogram_前1日",
    "MACD_Histogram_前2日",
    "MACD_綠柱趨緩接近翻紅",
    "是否符合 KD 區間",
    "是否符合 RSI 區間",
    "是否明顯放量",
    "MACD 是否綠柱趨緩接近翻紅",
    "法人近 5 日是否合計買超",
    "投信近 5 日是否買超",
    "外資近 1 日買賣超張數",
    "投信近 1 日買賣超張數",
    "自營商近 1 日買賣超張數",
    "三大法人近 1 日合計買賣超張數",
    "外資近 5 日買賣超張數",
    "投信近 5 日買賣超張數",
    "自營商近 5 日買賣超張數",
    "三大法人近 5 日合計買賣超張數",
    "外資近 20 日買賣超張數",
    "投信近 20 日買賣超張數",
    "自營商近 20 日買賣超張數",
    "三大法人近 20 日合計買賣超張數",
    "最後更新日期",
]


INSTITUTION_COLUMNS = [
    "外資近 1 日買賣超張數",
    "投信近 1 日買賣超張數",
    "自營商近 1 日買賣超張數",
    "三大法人近 1 日合計買賣超張數",
    "外資近 5 日買賣超張數",
    "投信近 5 日買賣超張數",
    "自營商近 5 日買賣超張數",
    "三大法人近 5 日合計買賣超張數",
    "外資近 20 日買賣超張數",
    "投信近 20 日買賣超張數",
    "自營商近 20 日買賣超張數",
    "三大法人近 20 日合計買賣超張數",
]


def add_error(errors: list[dict[str, str]], symbol: str, stage: str, reason: str) -> None:
    errors.append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "stage": stage,
            "reason": str(reason),
        }
    )


def fetch_official_stock_list(config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    try:
        return fetch_openapi_stock_list(config)
    except Exception:
        try:
            return fetch_mops_csv_stock_list(config)
        except Exception:
            return fetch_isin_stock_list(config)


def fetch_openapi_stock_list(config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    endpoints = [
        ("上市", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"),
        ("上櫃", "https://openapi.twse.com.tw/v1/opendata/t187ap03_O"),
    ]
    frames = []
    headers = {"User-Agent": "CandyTWStock/1.0"}

    for market, url in endpoints:
        response = requests.get(url, timeout=config["request_timeout_seconds"], headers=headers)
        response.raise_for_status()
        rows = response.json()
        raw = pd.DataFrame(rows)
        if raw.empty:
            continue

        code_col = next((col for col in ["公司代號", "股票代號", "證券代號", "Code"] if col in raw.columns), None)
        name_col = next((col for col in ["公司簡稱", "公司名稱", "股票名稱", "Name"] if col in raw.columns), None)
        if not code_col or not name_col:
            raise ValueError(f"{market} 股票清單欄位無法辨識")

        frame = pd.DataFrame(
            {
                "symbol": raw[code_col].astype(str).str.strip(),
                "name": raw[name_col].astype(str).str.strip(),
                "market": market,
            }
        )
        frames.append(frame)

    if not frames:
        raise ValueError("官方股票清單沒有資料")

    stocks = pd.concat(frames, ignore_index=True)
    stocks = stocks[stocks["symbol"].str.fullmatch(r"\d{4}", na=False)].copy()
    stocks = stocks.drop_duplicates(subset=["symbol", "market"]).reset_index(drop=True)
    return stocks


def fetch_mops_csv_stock_list(config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    endpoints = [
        ("上市", "https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv"),
        ("上櫃", "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"),
    ]
    frames = []
    headers = {"User-Agent": "CandyTWStock/1.0"}

    for market, url in endpoints:
        response = requests.get(url, timeout=config["request_timeout_seconds"], headers=headers)
        response.raise_for_status()
        response.encoding = "utf-8-sig"
        raw = pd.read_csv(StringIO(response.text), dtype=str)
        code_col = next((col for col in ["公司代號", "股票代號", "證券代號"] if col in raw.columns), None)
        name_col = next((col for col in ["公司簡稱", "公司名稱", "股票名稱"] if col in raw.columns), None)
        if not code_col or not name_col:
            raise ValueError(f"{market} MOPS CSV 欄位無法辨識")
        frames.append(
            pd.DataFrame(
                {
                    "symbol": raw[code_col].astype(str).str.strip(),
                    "name": raw[name_col].astype(str).str.strip(),
                    "market": market,
                }
            )
        )

    if not frames:
        raise ValueError("MOPS CSV 股票清單沒有資料")

    stocks = pd.concat(frames, ignore_index=True)
    stocks = stocks[stocks["symbol"].str.fullmatch(r"\d{4}", na=False)].copy()
    stocks = stocks.drop_duplicates(subset=["symbol", "market"]).reset_index(drop=True)
    return stocks


def fetch_isin_stock_list(config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    endpoints = [
        ("上市", "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"),
        ("上櫃", "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"),
    ]
    frames = []
    headers = {"User-Agent": "CandyTWStock/1.0"}

    for market, url in endpoints:
        response = requests.get(url, timeout=config["request_timeout_seconds"], headers=headers)
        response.raise_for_status()
        response.encoding = "big5"
        soup = BeautifulSoup(response.text, "html.parser")
        rows = []
        for tr in soup.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            first = cells[0].replace("\u3000", " ").strip()
            parts = first.split(maxsplit=1)
            if len(parts) < 2:
                continue
            symbol, name = parts[0].strip(), parts[1].strip()
            if symbol.isdigit() and len(symbol) == 4:
                rows.append({"symbol": symbol, "name": name, "market": market})
        frames.append(pd.DataFrame(rows))

    if not frames:
        raise ValueError("ISIN 股票清單沒有資料")

    stocks = pd.concat(frames, ignore_index=True)
    stocks = stocks.drop_duplicates(subset=["symbol", "market"]).reset_index(drop=True)
    return stocks


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype={"symbol": str})
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype={"symbol": str}, encoding="utf-8-sig")


def load_stock_list(config: dict[str, Any] = CONFIG, errors: list[dict[str, str]] | None = None) -> pd.DataFrame:
    path = Path(config["stock_list_path"])
    errors = errors if errors is not None else []

    if config.get("auto_refresh_stock_list", False):
        try:
            stocks = fetch_official_stock_list(config)
            path.parent.mkdir(parents=True, exist_ok=True)
            stocks.to_csv(path, index=False, encoding="utf-8-sig")
        except Exception as exc:  # noqa: BLE001
            add_error(errors, "ALL", "load_stock_list", f"官方股票清單抓取失敗，改用本機 CSV: {exc}")
            if not path.exists():
                raise FileNotFoundError(f"找不到股票清單: {path}") from exc
            stocks = read_csv_with_fallback(path)
    else:
        if not path.exists():
            raise FileNotFoundError(f"找不到股票清單: {path}")
        stocks = read_csv_with_fallback(path)

    required = {"symbol", "name", "market"}
    missing = required - set(stocks.columns)
    if missing:
        raise ValueError(f"股票清單缺少欄位: {', '.join(sorted(missing))}")

    stocks["symbol"] = stocks["symbol"].str.strip()
    stocks["name"] = stocks["name"].fillna("").astype(str).str.strip()
    stocks["market"] = stocks["market"].str.strip()
    stocks = stocks[stocks["market"].isin(["上市", "上櫃"])].copy()

    if config["exclude_etf"]:
        stocks = stocks[~stocks["name"].str.contains("ETF|ETN|指數", case=False, regex=True)]
    if config["exclude_warrant"]:
        stocks = stocks[stocks["symbol"].str.fullmatch(r"\d{4}")]
    if config["exclude_special_stock"]:
        stocks = stocks[~stocks["name"].str.contains("特別|甲特|乙特|丙特", regex=True)]
    if config.get("exclude_ky", False):
        stocks = stocks[~stocks["name"].str.contains("KY", case=False, regex=False)]

    if config.get("max_stocks"):
        stocks = stocks.head(int(config["max_stocks"]))

    return stocks.reset_index(drop=True)


def to_yfinance_ticker(symbol: str, market: str) -> str:
    suffix = ".TW" if market == "上市" else ".TWO"
    return f"{symbol}{suffix}"


def normalize_price_data(data: pd.DataFrame, config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    if data.empty:
        raise ValueError("yfinance 無資料")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(-1)

    data = data.rename(columns=str.title)
    needed = {"Open", "High", "Low", "Close", "Volume"}
    missing = needed - set(data.columns)
    if missing:
        raise ValueError(f"股價資料缺少欄位: {', '.join(sorted(missing))}")

    data = data.dropna(subset=["High", "Low", "Close", "Volume"]).copy()
    if len(data) < max(config["volume_long_window"], config["rsi_period"], config["kd_period"]) + 5:
        raise ValueError("股價資料筆數不足，無法計算指標")

    return data


def fetch_price_data(symbol: str, market: str, config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    ticker = to_yfinance_ticker(symbol, market)
    period = f"{config['price_history_months']}mo"
    data = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False)
    try:
        return normalize_price_data(data, config)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"{exc}: {ticker}") from exc


def chunked_dataframe(df: pd.DataFrame, size: int) -> list[pd.DataFrame]:
    return [df.iloc[start : start + size] for start in range(0, len(df), size)]


def extract_ticker_data(batch_data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if not isinstance(batch_data.columns, pd.MultiIndex):
        return batch_data.copy()

    level_0 = batch_data.columns.get_level_values(0)
    level_1 = batch_data.columns.get_level_values(1)
    if ticker in level_0:
        return batch_data[ticker].copy()
    if ticker in level_1:
        return batch_data.xs(ticker, axis=1, level=1).copy()
    return pd.DataFrame()


def build_technical_rows(stocks: pd.DataFrame, config: dict[str, Any], errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    technical_rows = []
    period = f"{config['price_history_months']}mo"
    batch_size = int(config["yfinance_batch_size"])

    stocks = stocks.copy()
    stocks["ticker"] = stocks.apply(lambda row: to_yfinance_ticker(row["symbol"], row["market"]), axis=1)

    for batch in chunked_dataframe(stocks, batch_size):
        tickers = batch["ticker"].tolist()
        try:
            batch_data = yf.download(
                tickers,
                period=period,
                interval="1d",
                group_by="ticker",
                progress=False,
                auto_adjust=False,
                threads=True,
            )
        except Exception as exc:  # noqa: BLE001
            for _, stock in batch.iterrows():
                add_error(errors, stock["symbol"], "fetch_price_data_batch", exc)
            continue

        for _, stock in batch.iterrows():
            try:
                raw = extract_ticker_data(batch_data, stock["ticker"])
                price_data = normalize_price_data(raw, config)
                indicators = calculate_indicators(price_data, config)
                technical_rows.append(build_technical_row(stock, indicators))
            except Exception as exc:  # noqa: BLE001
                add_error(errors, stock["symbol"], "technical_screening", exc)

        time.sleep(config["request_sleep_seconds"])

    return technical_rows


def calculate_indicators(price_data: pd.DataFrame, config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    df = price_data.copy()

    ma_period = config["ma_period"]
    kd_period = config["kd_period"]
    rsi_period = config["rsi_period"]

    low_min = df["Low"].rolling(kd_period, min_periods=kd_period).min()
    high_max = df["High"].rolling(kd_period, min_periods=kd_period).max()
    rsv = (df["Close"] - low_min) / (high_max - low_min) * 100
    rsv = rsv.replace([float("inf"), float("-inf")], pd.NA).fillna(50)

    df["K"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    df["D"] = df["K"].ewm(alpha=1 / 3, adjust=False).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / rsi_period, min_periods=rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, min_periods=rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI"] = df["RSI"].fillna(100)

    df["MA20"] = df["Close"].rolling(ma_period, min_periods=ma_period).mean()
    df["Volume_MA5"] = df["Volume"].rolling(config["volume_short_window"]).mean()
    df["Volume_MA20"] = df["Volume"].rolling(config["volume_mid_window"]).mean()
    df["Volume_MA40"] = df["Volume"].rolling(config["volume_long_window"]).mean()

    df["MACD_DIF"] = (
        df["Close"].ewm(span=config["macd_fast_period"], adjust=False).mean()
        - df["Close"].ewm(span=config["macd_slow_period"], adjust=False).mean()
    )
    df["MACD_Signal"] = df["MACD_DIF"].ewm(span=config["macd_signal_period"], adjust=False).mean()
    df["MACD_Histogram"] = df["MACD_DIF"] - df["MACD_Signal"]

    return df


def is_macd_green_bar_shrinking(indicators: pd.DataFrame, config: dict[str, Any] = CONFIG) -> bool:
    if len(indicators) < 3:
        return False

    h2 = indicators["MACD_Histogram"].iloc[-3]
    h1 = indicators["MACD_Histogram"].iloc[-2]
    h0 = indicators["MACD_Histogram"].iloc[-1]
    if pd.isna(h2) or pd.isna(h1) or pd.isna(h0):
        return False

    return bool(
        h0 < 0
        and h2 < h1 < h0
        and abs(h0) < abs(h1)
        and h0 > config["macd_near_zero_threshold"]
    )


def evaluate_strict_flags(row: pd.Series, config: dict[str, Any] = CONFIG) -> dict[str, bool]:
    kd_ok = config["kd_min"] <= row["K 值"] <= config["kd_max"] and config["kd_min"] <= row["D 值"] <= config["kd_max"]
    rsi_ok = config["rsi_min"] <= row["RSI"] <= config["rsi_max"]
    volume_mid_ok = row["Volume_MA5"] > row["Volume_MA20"] * config["volume_mid_multiplier"]
    volume_long_ok = row["Volume_MA5"] > row["Volume_MA40"] * config["volume_long_multiplier"]
    return {
        "price_ok": row["收盤價"] < config["price_limit"],
        "kd_ok": bool(kd_ok),
        "rsi_ok": bool(rsi_ok),
        "volume_mid_ok": bool(volume_mid_ok),
        "volume_long_ok": bool(volume_long_ok),
        "volume_ok": bool(volume_mid_ok and volume_long_ok),
        "k_above_d_ok": bool(row["K 值"] > row["D 值"]),
        "close_above_ma_ok": bool(row["收盤價"] > row["MA20"]),
    }


def apply_filters(indicators: pd.DataFrame, config: dict[str, Any] = CONFIG) -> bool:
    latest = indicators.iloc[-1]
    checks = [
        latest["Close"] < config["price_limit"],
        config["kd_min"] <= latest["K"] <= config["kd_max"],
        config["kd_min"] <= latest["D"] <= config["kd_max"],
        config["rsi_min"] <= latest["RSI"] <= config["rsi_max"],
        latest["Volume_MA5"] > latest["Volume_MA20"] * config["volume_mid_multiplier"],
        latest["Volume_MA5"] > latest["Volume_MA40"] * config["volume_long_multiplier"],
    ]

    if config["require_k_above_d"]:
        checks.append(latest["K"] > latest["D"])
    if config["require_close_above_ma20"]:
        checks.append(latest["Close"] > latest["MA20"])

    return bool(all(checks))


def build_technical_row(stock: pd.Series, indicators: pd.DataFrame) -> dict[str, Any]:
    latest = indicators.iloc[-1]
    prev1 = indicators.iloc[-2]
    prev2 = indicators.iloc[-3]
    volume_ratio = latest["Volume_MA5"] / latest["Volume_MA20"]
    macd_mark = is_macd_green_bar_shrinking(indicators)
    return {
        "股票代號": stock["symbol"],
        "股票名稱": stock["name"],
        "市場": stock["market"],
        "收盤價": latest["Close"],
        "MA20": latest["MA20"],
        "是否站上 MA20": bool(latest["Close"] > latest["MA20"]),
        "K 值": latest["K"],
        "D 值": latest["D"],
        "RSI": latest["RSI"],
        "Volume_MA5": latest["Volume_MA5"],
        "Volume_MA20": latest["Volume_MA20"],
        "Volume_MA40": latest["Volume_MA40"],
        "放量倍數": volume_ratio,
        "MACD_DIF": latest["MACD_DIF"],
        "MACD_Signal": latest["MACD_Signal"],
        "MACD_Histogram": latest["MACD_Histogram"],
        "MACD_Histogram_前1日": prev1["MACD_Histogram"],
        "MACD_Histogram_前2日": prev2["MACD_Histogram"],
        "MACD_綠柱趨緩接近翻紅": "是" if macd_mark else "否",
        "MACD 是否綠柱趨緩接近翻紅": "是" if macd_mark else "否",
        "最後更新日期": indicators.index[-1].strftime("%Y-%m-%d"),
    }


def iter_recent_dates(days: int) -> list[datetime]:
    today = datetime.now()
    return [today - timedelta(days=i) for i in range(days)]


def normalize_number(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).replace(",", "").replace("--", "0").strip()
    if text in {"", "-", "nan"}:
        return 0.0
    return float(text)


def shares_to_lots(value: Any) -> float:
    return normalize_number(value) / 1000


def first_existing(row: pd.Series, candidates: list[str]) -> Any:
    for column in candidates:
        if column in row.index:
            return row[column]
    return 0


def fetch_twse_institutional_by_date(date: datetime, config: dict[str, Any]) -> pd.DataFrame:
    date_text = date.strftime("%Y%m%d")
    url = "https://www.twse.com.tw/rwd/zh/fund/T86"
    params = {"date": date_text, "selectType": "ALLBUT0999", "response": "json"}
    response = requests.get(url, params=params, timeout=config["request_timeout_seconds"])
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data") or []
    fields = payload.get("fields") or []
    if not rows or not fields:
        return pd.DataFrame()

    raw = pd.DataFrame(rows, columns=fields)
    result = pd.DataFrame()
    result["symbol"] = raw["證券代號"].astype(str).str.strip()
    result["date"] = date.strftime("%Y-%m-%d")
    result["外資買賣超張數"] = raw.apply(
        lambda row: shares_to_lots(first_existing(row, ["外陸資買賣超股數(不含外資自營商)", "外資及陸資買賣超股數"])),
        axis=1,
    )
    result["投信買賣超張數"] = raw.apply(lambda row: shares_to_lots(first_existing(row, ["投信買賣超股數"])), axis=1)
    dealer_self = raw.apply(lambda row: shares_to_lots(first_existing(row, ["自營商買賣超股數(自行買賣)"])), axis=1)
    dealer_hedge = raw.apply(lambda row: shares_to_lots(first_existing(row, ["自營商買賣超股數(避險)"])), axis=1)
    dealer_total = raw.apply(lambda row: shares_to_lots(first_existing(row, ["自營商買賣超股數"])), axis=1)
    result["自營商買賣超張數"] = dealer_total.where(dealer_total != 0, dealer_self + dealer_hedge)
    result["三大法人合計買賣超張數"] = (
        result["外資買賣超張數"] + result["投信買賣超張數"] + result["自營商買賣超張數"]
    )
    return result


def fetch_tpex_institutional_by_date(date: datetime, config: dict[str, Any]) -> pd.DataFrame:
    roc_date = f"{date.year - 1911}/{date.month:02d}/{date.day:02d}"
    url = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"
    params = {"date": roc_date, "type": "Daily", "response": "json"}
    response = requests.get(url, params=params, timeout=config["request_timeout_seconds"])
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("tables", [{}])[0].get("data") or payload.get("data") or []
    fields = payload.get("tables", [{}])[0].get("fields") or payload.get("fields") or []
    if not rows:
        return pd.DataFrame()

    raw = pd.DataFrame(rows, columns=fields if fields and len(fields) == len(rows[0]) else None)
    if raw.empty:
        return pd.DataFrame()

    result = pd.DataFrame()
    symbol_col = "代號" if "代號" in raw.columns else raw.columns[0]
    result["symbol"] = raw[symbol_col].astype(str).str.strip()
    result["date"] = date.strftime("%Y-%m-%d")

    result["外資買賣超張數"] = raw.apply(
        lambda row: normalize_number(first_existing(row, ["外資及陸資(不含外資自營商)買賣超股數", "外資及陸資買賣超股數", "外資買賣超股數", "外資買賣超"])),
        axis=1,
    )
    result["投信買賣超張數"] = raw.apply(lambda row: normalize_number(first_existing(row, ["投信買賣超股數", "投信買賣超"])), axis=1)
    result["自營商買賣超張數"] = raw.apply(
        lambda row: normalize_number(first_existing(row, ["自營商買賣超股數", "自營商買賣超"])),
        axis=1,
    )

    # TPEx dailyTrade values are normally reported in shares on newer JSON feeds.
    for column in ["外資買賣超張數", "投信買賣超張數", "自營商買賣超張數"]:
        if result[column].abs().max() > 100000:
            result[column] = result[column] / 1000

    result["三大法人合計買賣超張數"] = (
        result["外資買賣超張數"] + result["投信買賣超張數"] + result["自營商買賣超張數"]
    )
    return result


def fetch_institutional_data(
    stocks: pd.DataFrame,
    config: dict[str, Any] = CONFIG,
    errors: list[dict[str, str]] | None = None,
) -> pd.DataFrame:
    errors = errors if errors is not None else []
    frames: list[pd.DataFrame] = []

    for market, fetcher in [("上市", fetch_twse_institutional_by_date), ("上櫃", fetch_tpex_institutional_by_date)]:
        wanted_symbols = set(stocks.loc[stocks["market"] == market, "symbol"])
        if not wanted_symbols:
            continue

        market_frames = []
        consecutive_failures = 0
        for date in iter_recent_dates(config["institutional_lookback_calendar_days"]):
            try:
                daily = fetcher(date, config)
                consecutive_failures = 0
                if not daily.empty:
                    daily = daily[daily["symbol"].isin(wanted_symbols)]
                    if not daily.empty:
                        market_frames.append(daily)
                if len(market_frames) >= 20:
                    break
                time.sleep(config["request_sleep_seconds"])
            except Exception as exc:  # noqa: BLE001
                consecutive_failures += 1
                add_error(errors, market, "fetch_institutional_data", f"{date:%Y-%m-%d}: {exc}")
                if consecutive_failures >= config["institutional_max_consecutive_failures"]:
                    add_error(errors, market, "fetch_institutional_data", "連續抓取失敗，停止此市場法人資料抓取")
                    break

        if market_frames:
            frames.append(pd.concat(market_frames, ignore_index=True))

    if not frames:
        return pd.DataFrame(columns=["symbol", "date", "外資買賣超張數", "投信買賣超張數", "自營商買賣超張數", "三大法人合計買賣超張數"])

    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values(["symbol", "date"], ascending=[True, False])
    return data


def summarize_institutional_data(institutional_data: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        symbol_data = institutional_data[institutional_data["symbol"] == symbol].copy()
        row: dict[str, Any] = {"股票代號": symbol}
        for window in [1, 5, 20]:
            recent = symbol_data.head(window)
            row[f"外資近 {window} 日買賣超張數"] = recent["外資買賣超張數"].sum() if not recent.empty else 0
            row[f"投信近 {window} 日買賣超張數"] = recent["投信買賣超張數"].sum() if not recent.empty else 0
            row[f"自營商近 {window} 日買賣超張數"] = recent["自營商買賣超張數"].sum() if not recent.empty else 0
            row[f"三大法人近 {window} 日合計買賣超張數"] = recent["三大法人合計買賣超張數"].sum() if not recent.empty else 0
        rows.append(row)
    return pd.DataFrame(rows)


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def evaluate_watch_flags(row: pd.Series, config: dict[str, Any] = CONFIG) -> dict[str, bool]:
    return {
        "price_ok": bool(row["收盤價"] < config["price_limit"]),
        "kd_watch_ok": bool(
            config["watch_kd_min"] <= row["K 值"] <= config["watch_kd_max"]
            and config["watch_kd_min"] <= row["D 值"] <= config["watch_kd_max"]
        ),
        "rsi_watch_ok": bool(config["watch_rsi_min"] <= row["RSI"] <= config["watch_rsi_max"]),
        "volume_mid_watch_ok": bool(row["Volume_MA5"] > row["Volume_MA20"] * config["watch_volume_mid_multiplier"]),
        "volume_long_watch_ok": bool(row["Volume_MA5"] > row["Volume_MA40"] * config["watch_volume_long_multiplier"]),
        "macd_watch_ok": bool(row["MACD_綠柱趨緩接近翻紅"] == "是"),
        "institution_watch_ok": bool(
            row["三大法人近 5 日合計買賣超張數"] > 0 or row["投信近 5 日買賣超張數"] > 0
        ),
    }


def calculate_candidate_score(row: pd.Series, config: dict[str, Any] = CONFIG) -> int:
    strict_flags = evaluate_strict_flags(row, config)
    score = 0
    if strict_flags["kd_ok"]:
        score += 20
    if strict_flags["rsi_ok"]:
        score += 20
    if strict_flags["volume_mid_ok"]:
        score += 20
    if strict_flags["volume_long_ok"]:
        score += 10
    if row["MACD_綠柱趨緩接近翻紅"] == "是":
        score += 10
    if row["三大法人近 5 日合計買賣超張數"] > 0:
        score += 10
    if row["投信近 5 日買賣超張數"] > 0:
        score += 10
    return score


def classify_candidates(merged: pd.DataFrame, config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    if merged.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    rows = []
    for _, row in merged.iterrows():
        strict_flags = evaluate_strict_flags(row, config)
        watch_flags = evaluate_watch_flags(row, config)

        strict_ok = all(
            [
                strict_flags["price_ok"],
                strict_flags["kd_ok"],
                strict_flags["k_above_d_ok"],
                strict_flags["rsi_ok"],
                strict_flags["volume_mid_ok"],
                strict_flags["volume_long_ok"],
            ]
        )
        if config["require_close_above_ma20"]:
            strict_ok = strict_ok and strict_flags["close_above_ma_ok"]

        watch_count = sum(watch_flags.values())
        watch_ok = watch_count >= config["watch_min_conditions"]

        if strict_ok:
            candidate_level = "符合"
        elif watch_ok:
            candidate_level = "接近"
        else:
            continue

        out = row.to_dict()
        out["candidate_level"] = candidate_level
        out["candidate_score"] = calculate_candidate_score(row, config)
        out["是否符合 KD 區間"] = yes_no(strict_flags["kd_ok"])
        out["是否符合 RSI 區間"] = yes_no(strict_flags["rsi_ok"])
        out["是否明顯放量"] = yes_no(strict_flags["volume_ok"])
        out["法人近 5 日是否合計買超"] = yes_no(row["三大法人近 5 日合計買賣超張數"] > 0)
        out["投信近 5 日是否買超"] = yes_no(row["投信近 5 日買賣超張數"] > 0)
        rows.append(out)

    result = pd.DataFrame(rows)
    if result.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    result = result[OUTPUT_COLUMNS]
    result = result.sort_values(
        by=["candidate_score", "放量倍數", "三大法人近 5 日合計買賣超張數", "投信近 5 日買賣超張數", "RSI"],
        ascending=[False, False, False, False, True],
    )
    return result.reset_index(drop=True)


def merge_result(technical_result: pd.DataFrame, institutional_summary: pd.DataFrame) -> pd.DataFrame:
    if technical_result.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    merged = technical_result.merge(institutional_summary, on="股票代號", how="left")
    for column in INSTITUTION_COLUMNS:
        if column not in merged.columns:
            merged[column] = 0
        merged[column] = merged[column].fillna(0)

    return classify_candidates(merged)


def format_number(value: Any, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    return str(value)


def build_html_table(data: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    if data.empty:
        return '<div class="empty">目前沒有符合此分類的股票。</div>'

    display = data.head(max_rows) if max_rows else data
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    rows = []
    for _, row in display.iterrows():
        cells = []
        for column in columns:
            value = row.get(column, "")
            class_name = ""
            if column == "candidate_level":
                class_name = f' class="level level-{html.escape(str(value))}"'
            elif column in {"MACD_綠柱趨緩接近翻紅", "法人近 5 日是否合計買超", "投信近 5 日是否買超"}:
                class_name = ' class="yes"' if value == "是" else ' class="no"'
            cells.append(f"<td{class_name}>{html.escape(format_number(value))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def export_html(result: pd.DataFrame, config: dict[str, Any] = CONFIG) -> None:
    path = Path(config["html_output_path"])
    path.parent.mkdir(parents=True, exist_ok=True)

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    strict = result[result["candidate_level"] == "符合"].copy() if not result.empty else result
    watch = result[result["candidate_level"] == "接近"].copy() if not result.empty else result
    top = result.head(30).copy() if not result.empty else result

    columns = [
        "candidate_level",
        "candidate_score",
        "股票代號",
        "股票名稱",
        "市場",
        "收盤價",
        "K 值",
        "D 值",
        "RSI",
        "放量倍數",
        "MACD_綠柱趨緩接近翻紅",
        "三大法人近 5 日合計買賣超張數",
        "投信近 5 日買賣超張數",
        "最後更新日期",
    ]

    styles = """
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #60717d;
      --line: #d7e0e5;
      --bg: #f6f8f9;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-soft: #e5f4f2;
      --warn: #9a5b00;
      --warn-soft: #fff4df;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    header {
      padding: 28px 32px 18px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }
    h2 { margin: 32px 0 12px; font-size: 20px; letter-spacing: 0; }
    .subtitle { color: var(--muted); margin: 0; }
    main { padding: 24px 32px 40px; }
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .label { color: var(--muted); font-size: 13px; margin-bottom: 8px; }
    .value { font-size: 28px; font-weight: 700; }
    .table-wrap {
      overflow: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    table { border-collapse: collapse; width: 100%; min-width: 1120px; }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: right;
      white-space: nowrap;
      font-size: 14px;
    }
    th {
      position: sticky;
      top: 0;
      background: #edf3f5;
      color: #33434d;
      font-size: 12px;
      font-weight: 700;
    }
    td:nth-child(1), td:nth-child(3), td:nth-child(4), td:nth-child(5), th:nth-child(1), th:nth-child(3), th:nth-child(4), th:nth-child(5) {
      text-align: left;
    }
    tr:hover { background: #f8fbfc; }
    .level, .yes, .no {
      font-weight: 700;
    }
    .level-符合, .yes {
      color: var(--accent);
    }
    .level-接近 {
      color: var(--warn);
    }
    .no {
      color: var(--muted);
    }
    .empty {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      color: var(--muted);
    }
    .note {
      margin-top: 18px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    """

    document = f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>台股低位轉強放量候選清單</title>
  <style>{styles}</style>
</head>
<body>
  <header>
    <h1>台股低位轉強放量候選清單</h1>
    <p class="subtitle">更新時間：{html.escape(updated_at)}。依 candidate_score、放量倍數與法人買超排序。</p>
  </header>
  <main>
    <section class="cards">
      <div class="card"><div class="label">總候選</div><div class="value">{len(result):,}</div></div>
      <div class="card"><div class="label">嚴格符合</div><div class="value">{len(strict):,}</div></div>
      <div class="card"><div class="label">接近觀察</div><div class="value">{len(watch):,}</div></div>
      <div class="card"><div class="label">最高分</div><div class="value">{int(result['candidate_score'].max()) if not result.empty else 0}</div></div>
    </section>

    <h2>優先觀察 Top 30</h2>
    <div class="table-wrap">{build_html_table(top, columns)}</div>

    <h2>嚴格符合</h2>
    <div class="table-wrap">{build_html_table(strict, columns)}</div>

    <h2>接近觀察</h2>
    <div class="table-wrap">{build_html_table(watch, columns, max_rows=120)}</div>

    <p class="note">本頁為量化條件整理，不構成投資建議。MACD 僅為參考標註，不作為硬性篩選條件。</p>
  </main>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def export_result(result: pd.DataFrame, config: dict[str, Any] = CONFIG) -> None:
    csv_path = Path(config["output_csv_path"])
    excel_path = Path(config["output_excel_path"])
    strict_path = Path(config["strict_output_excel_path"])
    watchlist_path = Path(config["watchlist_output_excel_path"])
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(csv_path, index=False, encoding="utf-8-sig")
    result.to_excel(excel_path, index=False)
    result[result["candidate_level"] == "符合"].to_excel(strict_path, index=False)
    result[result["candidate_level"] == "接近"].to_excel(watchlist_path, index=False)
    export_html(result, config)


def write_error_log(errors: list[dict[str, str]], config: dict[str, Any] = CONFIG) -> None:
    path = Path(config["error_log_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["timestamp", "symbol", "stage", "reason"]
    pd.DataFrame(errors, columns=columns).to_csv(path, index=False, encoding="utf-8-sig")


def run_screener(config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    errors: list[dict[str, str]] = []
    stocks = load_stock_list(config, errors)
    technical_rows = build_technical_rows(stocks, config, errors)

    technical_result = pd.DataFrame(technical_rows)

    if technical_result.empty:
        institutional_summary = pd.DataFrame(columns=["股票代號"])
    else:
        candidate_stocks = stocks[stocks["symbol"].isin(technical_result["股票代號"])]
        try:
            institutional_data = fetch_institutional_data(candidate_stocks, config, errors)
            institutional_summary = summarize_institutional_data(institutional_data, candidate_stocks["symbol"].tolist())
        except Exception as exc:  # noqa: BLE001
            add_error(errors, "ALL", "fetch_institutional_data", exc)
            institutional_summary = pd.DataFrame({"股票代號": candidate_stocks["symbol"].tolist()})

    result = merge_result(technical_result, institutional_summary)
    export_result(result, config)
    write_error_log(errors, config)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="台股低位轉強放量選股器 MVP")
    parser.add_argument("--stock-list", help="覆寫股票清單 CSV 路徑")
    parser.add_argument("--require-close-above-ma20", action="store_true", help="啟用 Close > MA20 條件")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CONFIG.copy()
    if args.stock_list:
        config["stock_list_path"] = args.stock_list
    if args.require_close_above_ma20:
        config["require_close_above_ma20"] = True

    result = run_screener(config)
    print(f"完成篩選，共 {len(result)} 檔符合條件。")
    print(f"CSV: {config['output_csv_path']}")
    print(f"Excel: {config['output_excel_path']}")
    print(f"錯誤紀錄: {config['error_log_path']}")


if __name__ == "__main__":
    main()
