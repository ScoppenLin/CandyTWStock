from config import MARKET_WEIGHTS, POSITION_RULES


def _score_trend(close, ma20):
    if close >= ma20 * 1.02:
        return 100
    if close >= ma20:
        return 80
    if close >= ma20 * 0.98:
        return 50
    return 20


def _score_volume(volume_ratio):
    if volume_ratio >= 1.2:
        return 100
    if volume_ratio >= 1.0:
        return 75
    if volume_ratio >= 0.8:
        return 50
    return 20


def _score_limit_balance(limit_up_count, limit_down_count):
    if limit_down_count == 0:
        return 100
    ratio = limit_up_count / limit_down_count
    if ratio >= 5:
        return 100
    if ratio >= 2:
        return 75
    if ratio >= 1:
        return 50
    return 20


def analyze_market(market):
    taiex = market["taiex"]
    otc = market["otc"]
    tsmc = market["tsmc"]

    components = {
        "taiex_trend": _score_trend(taiex["close"], taiex["ma20"]),
        "otc_trend": _score_trend(otc["close"], otc["ma20"]),
        "tsmc_trend": _score_trend(tsmc["close"], tsmc["ma20"]),
        "market_volume": _score_volume((taiex["volume_ratio"] + otc["volume_ratio"]) / 2),
        "limit_balance": _score_limit_balance(market["limit_up_count"], market["limit_down_count"]),
    }
    score = round(sum(components[k] * w for k, w in MARKET_WEIGHTS.items()) / 100)

    if score >= 75:
        state = "偏多"
    elif score >= 60:
        state = "中性偏多"
    elif score >= 45:
        state = "震盪"
    else:
        state = "偏空"

    position = next(position for threshold, position in POSITION_RULES if score >= threshold)
    return {
        "state": state,
        "score": score,
        "suggested_position": position,
        "components": components,
    }
