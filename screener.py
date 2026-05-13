from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yfinance as yf

from config import CONFIG


OUTPUT_COLUMNS = [
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


def load_stock_list(config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    path = Path(config["stock_list_path"])
    if not path.exists():
        raise FileNotFoundError(f"找不到股票清單: {path}")

    stocks = pd.read_csv(path, dtype={"symbol": str})
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

    return stocks.reset_index(drop=True)


def to_yfinance_ticker(symbol: str, market: str) -> str:
    suffix = ".TW" if market == "上市" else ".TWO"
    return f"{symbol}{suffix}"


def fetch_price_data(symbol: str, market: str, config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    ticker = to_yfinance_ticker(symbol, market)
    period = f"{config['price_history_months']}mo"
    data = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False)

    if data.empty:
        raise ValueError(f"yfinance 無資料: {ticker}")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.rename(columns=str.title)
    needed = {"Open", "High", "Low", "Close", "Volume"}
    missing = needed - set(data.columns)
    if missing:
        raise ValueError(f"股價資料缺少欄位: {', '.join(sorted(missing))}")

    data = data.dropna(subset=["High", "Low", "Close", "Volume"]).copy()
    if len(data) < max(config["volume_long_window"], config["rsi_period"], config["kd_period"]) + 5:
        raise ValueError("股價資料筆數不足，無法計算指標")

    return data


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

    return df


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
    volume_ratio = latest["Volume_MA5"] / latest["Volume_MA20"]
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


def merge_result(technical_result: pd.DataFrame, institutional_summary: pd.DataFrame) -> pd.DataFrame:
    if technical_result.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    merged = technical_result.merge(institutional_summary, on="股票代號", how="left")
    for column in INSTITUTION_COLUMNS:
        if column not in merged.columns:
            merged[column] = 0
        merged[column] = merged[column].fillna(0)

    merged = merged[OUTPUT_COLUMNS]
    merged = merged.sort_values(
        by=["放量倍數", "三大法人近 5 日合計買賣超張數", "投信近 5 日買賣超張數", "RSI"],
        ascending=[False, False, False, True],
    )
    return merged.reset_index(drop=True)


def export_result(result: pd.DataFrame, config: dict[str, Any] = CONFIG) -> None:
    csv_path = Path(config["output_csv_path"])
    excel_path = Path(config["output_excel_path"])
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(csv_path, index=False, encoding="utf-8-sig")
    result.to_excel(excel_path, index=False)


def write_error_log(errors: list[dict[str, str]], config: dict[str, Any] = CONFIG) -> None:
    path = Path(config["error_log_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["timestamp", "symbol", "stage", "reason"]
    pd.DataFrame(errors, columns=columns).to_csv(path, index=False, encoding="utf-8-sig")


def run_screener(config: dict[str, Any] = CONFIG) -> pd.DataFrame:
    errors: list[dict[str, str]] = []
    stocks = load_stock_list(config)
    technical_rows = []

    for _, stock in stocks.iterrows():
        symbol = stock["symbol"]
        try:
            price_data = fetch_price_data(symbol, stock["market"], config)
            indicators = calculate_indicators(price_data, config)
            if apply_filters(indicators, config):
                technical_rows.append(build_technical_row(stock, indicators))
        except Exception as exc:  # noqa: BLE001
            add_error(errors, symbol, "technical_screening", exc)

        time.sleep(config["request_sleep_seconds"])

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
