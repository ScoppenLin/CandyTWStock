CONFIG = {
    "price_limit": 300,
    "kd_min": 30,
    "kd_max": 50,
    "rsi_min": 30,
    "rsi_max": 50,
    "kd_period": 9,
    "rsi_period": 14,
    "ma_period": 20,
    "volume_short_window": 5,
    "volume_mid_window": 20,
    "volume_long_window": 40,
    "volume_mid_multiplier": 1.5,
    "volume_long_multiplier": 1.3,
    "require_k_above_d": True,
    "require_close_above_ma20": False,
    "price_history_months": 3,
    "exclude_etf": True,
    "exclude_warrant": True,
    "exclude_special_stock": True,
    "exclude_ky": False,
    "stock_list_path": "data/stock_list.csv",
    "output_csv_path": "output/screening_result.csv",
    "output_excel_path": "output/screening_result.xlsx",
    "error_log_path": "logs/error_log.csv",
    "institutional_lookback_calendar_days": 45,
    "institutional_max_consecutive_failures": 3,
    "request_timeout_seconds": 15,
    "request_sleep_seconds": 0.25,
}


# Legacy constants kept so the earlier CandyStock MVP modules in this folder
# can still import config.py without breaking.
MARKET_WEIGHTS = {
    "taiex_trend": 25,
    "otc_trend": 25,
    "tsmc_trend": 15,
    "market_volume": 15,
    "limit_balance": 20,
}

STOCK_SCORE_WEIGHTS = {
    "volume_ratio": 30,
    "ma_trend": 25,
    "rsi": 10,
    "macd": 10,
    "sector_heat": 15,
    "institutional": 10,
}

SECTOR_HEAT_WEIGHTS = {
    "turnover": 40,
    "limit_up_count": 30,
    "avg_change_pct": 20,
    "relative_volume": 10,
}

POSITION_RULES = [
    (80, 0.8),
    (70, 0.7),
    (60, 0.5),
    (0, 0.3),
]

WATCHLIST = ["3550", "3017", "6218", "2330", "2382", "8046"]
