from config import SECTOR_HEAT_WEIGHTS


def _normalize(value, high, low=0):
    if high == low:
        return 0
    score = (value - low) / (high - low) * 100
    return max(0, min(100, score))


def rank_sectors(sectors):
    max_turnover = max(item["turnover"] for item in sectors)
    max_limit_up = max(item["limit_up_count"] for item in sectors) or 1
    max_change = max(item["avg_change_pct"] for item in sectors)
    min_change = min(item["avg_change_pct"] for item in sectors)
    max_relative_volume = max(item["relative_volume"] for item in sectors)

    ranked = []
    for item in sectors:
        components = {
            "turnover": _normalize(item["turnover"], max_turnover),
            "limit_up_count": _normalize(item["limit_up_count"], max_limit_up),
            "avg_change_pct": _normalize(item["avg_change_pct"], max_change, min_change),
            "relative_volume": _normalize(item["relative_volume"], max_relative_volume),
        }
        heat_score = round(sum(components[k] * w for k, w in SECTOR_HEAT_WEIGHTS.items()) / 100)
        ranked.append({**item, "heat_score": heat_score, "components": components})

    return sorted(ranked, key=lambda item: item["heat_score"], reverse=True)
