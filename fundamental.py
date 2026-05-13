def fundamental_penalty(stock):
    penalty = 0
    reasons = []

    if stock["eps_ttm"] < 0:
        penalty += 20
        reasons.append("EPS 連續虧損")
    elif stock["eps_ttm"] < 1:
        penalty += 8
        reasons.append("EPS 偏低")

    if stock["revenue_yoy"] < -10:
        penalty += 15
        reasons.append("營收明顯衰退")
    elif stock["revenue_yoy"] < 0:
        penalty += 8
        reasons.append("營收年減")

    if stock["gross_margin"] < 10:
        penalty += 8
        reasons.append("毛利率偏低")

    return penalty, reasons
