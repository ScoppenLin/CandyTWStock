from data_provider import load_daily_snapshot
from market import analyze_market
from report import build_report
from risk_control import analyze_risk
from sector import rank_sectors
from stock_score import score_stocks


def main():
    snapshot = load_daily_snapshot()
    market_result = analyze_market(snapshot["market"])
    sector_rankings = rank_sectors(snapshot["sectors"])
    stock_results = score_stocks(snapshot["stocks"], sector_rankings)
    risk_result = analyze_risk(snapshot, market_result, sector_rankings)
    print(build_report(snapshot, market_result, sector_rankings, stock_results, risk_result))


if __name__ == "__main__":
    main()
