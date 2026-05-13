def analyze_risk(snapshot, market_result, sector_rankings):
    risks = []
    market = snapshot["market"]

    if market["otc"]["close"] < market["otc"]["ma20"]:
        risks.append("OTC 跌破月線")

    if market["taiex"]["close"] < market["taiex"]["ma20"]:
        risks.append("大盤跌破月線")

    if market["limit_up_count"] < market["limit_down_count"] * 2:
        risks.append("漲停家數優勢不足")

    weak_hot_sectors = [
        item["name"]
        for item in sector_rankings[:3]
        if item["avg_change_pct"] < 0 or item["relative_volume"] < 0.9
    ]
    for sector in weak_hot_sectors:
        risks.append(f"{sector} 主流動能轉弱")

    if market_result["score"] < 60:
        risks.append("市場分數低於可積極做多區")

    if risks:
        adjusted_position = min(market_result["suggested_position"], 0.5)
    else:
        adjusted_position = market_result["suggested_position"]

    return {
        "risks": risks,
        "position": adjusted_position,
        "cash": round(1 - adjusted_position, 2),
    }
