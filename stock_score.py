from config import STOCK_SCORE_WEIGHTS
from fundamental import fundamental_penalty


def _score_volume_ratio(value):
    if value >= 2:
        return 100
    if value >= 1.5:
        return 80
    if value >= 1.1:
        return 60
    if value >= 0.8:
        return 40
    return 20


def _score_ma_trend(close, ma20):
    if close >= ma20 * 1.05:
        return 100
    if close >= ma20 * 1.02:
        return 80
    if close >= ma20:
        return 60
    if close >= ma20 * 0.97:
        return 40
    return 20


def _score_rsi(rsi):
    if 55 <= rsi <= 72:
        return 100
    if 50 <= rsi < 55 or 72 < rsi <= 78:
        return 70
    if 45 <= rsi < 50:
        return 45
    return 25


def _score_macd(macd_hist):
    if macd_hist > 0.5:
        return 100
    if macd_hist > 0:
        return 75
    if macd_hist > -0.2:
        return 45
    return 20


def _score_institutional(days):
    if days >= 4:
        return 100
    if days >= 2:
        return 80
    if days >= 0:
        return 55
    return 25


def score_stocks(stocks, sector_rankings):
    sector_scores = {item["name"]: item["heat_score"] for item in sector_rankings}
    results = []

    for stock in stocks:
        components = {
            "volume_ratio": _score_volume_ratio(stock["volume_ratio"]),
            "ma_trend": _score_ma_trend(stock["close"], stock["ma20"]),
            "rsi": _score_rsi(stock["rsi"]),
            "macd": _score_macd(stock["macd_hist"]),
            "sector_heat": sector_scores.get(stock["sector"], 40),
            "institutional": _score_institutional(stock["institutional_buy_days"]),
        }
        raw_score = sum(components[k] * w for k, w in STOCK_SCORE_WEIGHTS.items()) / 100
        penalty, fundamental_flags = fundamental_penalty(stock)
        score = max(0, round(raw_score - penalty))

        if score >= 80:
            strength = "主升段"
            action = "續抱／找回測進場"
        elif score >= 60:
            strength = "偏強"
            action = "觀察低風險進場"
        elif score >= 40:
            strength = "觀察"
            action = "不追高，等待轉強"
        else:
            strength = "弱勢"
            action = "減碼／避開"

        signals = []
        if stock["volume_ratio"] >= 1.5:
            signals.append("爆量")
        if stock["close"] >= stock["ma20"]:
            signals.append("站上月線")
        if sector_scores.get(stock["sector"], 0) >= 70:
            signals.append("主流題材")
        if stock["institutional_buy_days"] >= 2:
            signals.append("法人連買")

        results.append({
            **stock,
            "score": score,
            "strength": strength,
            "action": action,
            "signals": signals,
            "fundamental_flags": fundamental_flags,
            "components": components,
        })

    return sorted(results, key=lambda item: item["score"], reverse=True)
