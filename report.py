def _pct(value):
    return f"{round(value * 100)}%"


def build_report(snapshot, market_result, sector_rankings, stock_results, risk_result):
    leaders = sector_rankings[:3]
    strong_stocks = [item for item in stock_results if item["score"] >= 60][:5]
    risks = risk_result["risks"] or ["無明顯系統性風險"]

    lines = [
        f"台股市場資金決策系統 MVP | {snapshot['date']}",
        "",
        "【市場】",
        f"市場狀態：{market_result['state']}（{market_result['score']}）",
        f"建議持股：{_pct(risk_result['position'])}",
        f"現金比例：{_pct(risk_result['cash'])}",
        "",
        "【主流族群】",
    ]

    for idx, sector in enumerate(leaders, start=1):
        lines.append(
            f"{idx}. {sector['name']} | 熱度 {sector['heat_score']} | "
            f"成交值 {sector['turnover']} 億 | 平均漲跌 {sector['avg_change_pct']}%"
        )

    lines.extend(["", "【強勢股】"])
    for stock in strong_stocks:
        signal_text = "、".join(stock["signals"]) if stock["signals"] else "無明顯訊號"
        lines.append(
            f"{stock['symbol']} {stock['name']} | {stock['sector']} | "
            f"分數 {stock['score']} | {stock['strength']} | {stock['action']} | {signal_text}"
        )

    lines.extend(["", "【風險】"])
    for risk in risks:
        lines.append(f"- {risk}")

    lines.extend(["", "【建議】"])
    if market_result["score"] >= 75 and not risk_result["risks"]:
        lines.append("✔ 可偏積極做多")
    elif market_result["score"] >= 60:
        lines.append("✔ 可做多，但控制追價")
    else:
        lines.append("✔ 降低持股，等待市場轉強")
    lines.append(f"✔ 留 {_pct(risk_result['cash'])} 現金")
    lines.append("✔ 聚焦前三大主流族群，弱勢族群減碼")
    lines.append("✔ 不追高開或長黑跌破月線個股")

    return "\n".join(lines)
