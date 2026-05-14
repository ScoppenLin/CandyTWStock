from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import pandas as pd


DEFAULT_RECIPIENTS = "huiju999@yahoo.com.tw,scoppen.lin@gmail.com"
DEFAULT_SITE_URL = "https://scoppenlin.github.io/CandyTWStock/"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Email notification skipped: {name} must be a number, got {raw!r}.")
        return default


def _split_recipients(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def _format_number(value: object, digits: int = 2) -> str:
    if pd.isna(value):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.{digits}f}"


def _build_table(df: pd.DataFrame) -> str:
    columns = [
        "股票代號",
        "股票名稱",
        "市場",
        "candidate_level",
        "candidate_score",
        "收盤價",
        "K 值",
        "D 值",
        "RSI",
        "放量倍數",
        "投信近 5 日買賣超張數",
        "三大法人近 5 日合計買賣超張數",
        "MACD_綠柱趨緩接近翻紅",
    ]
    available_columns = [column for column in columns if column in df.columns]
    if df.empty or not available_columns:
        return "<p>今天沒有符合目前條件的候選股票。</p>"

    rows = []
    for _, row in df.head(15).iterrows():
        cells = []
        for column in available_columns:
            value = row[column]
            if column in {"candidate_score"}:
                text = _format_number(value, 0)
            elif column in {"收盤價", "K 值", "D 值", "RSI", "放量倍數"}:
                text = _format_number(value, 2)
            else:
                text = "" if pd.isna(value) else str(value)
            cells.append(f"<td>{text}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    header = "".join(f"<th>{column}</th>" for column in available_columns)
    return f"""
    <table>
      <thead><tr>{header}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _build_message(result_path: Path, site_url: str) -> tuple[str, str]:
    if not result_path.exists():
        return (
            "台股低位轉強放量選股器：今日沒有產生結果檔",
            f"""
            <p>今天的 GitHub Actions 已完成，但找不到 <code>{result_path}</code>。</p>
            <p>請到 GitHub Actions 檢查執行紀錄。</p>
            <p>網頁：<a href="{site_url}">{site_url}</a></p>
            """,
        )

    df = pd.read_csv(result_path)
    strict_count = int((df.get("candidate_level") == "符合").sum()) if "candidate_level" in df.columns else 0
    watch_count = int((df.get("candidate_level") == "接近").sum()) if "candidate_level" in df.columns else len(df)
    updated_at = ""
    if "最後更新日期" in df.columns and not df.empty:
        updated_at = str(df["最後更新日期"].dropna().iloc[0]) if not df["最後更新日期"].dropna().empty else ""

    subject_date = f" {updated_at}" if updated_at else ""
    subject = f"台股低位轉強放量選股器{subject_date}：符合 {strict_count} 檔 / 接近 {watch_count} 檔"
    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; line-height: 1.5; }}
          a {{ color: #1f6feb; }}
          table {{ border-collapse: collapse; width: 100%; margin-top: 16px; font-size: 13px; }}
          th, td {{ border: 1px solid #d0d7de; padding: 6px 8px; text-align: right; white-space: nowrap; }}
          th {{ background: #f6f8fa; }}
          th:nth-child(1), th:nth-child(2), th:nth-child(3), th:nth-child(4),
          td:nth-child(1), td:nth-child(2), td:nth-child(3), td:nth-child(4) {{ text-align: left; }}
          .summary {{ margin: 16px 0; padding: 12px 14px; background: #f6f8fa; border: 1px solid #d0d7de; }}
        </style>
      </head>
      <body>
        <h2>台股低位轉強放量選股器</h2>
        <div class="summary">
          <div>嚴格符合：<strong>{strict_count}</strong> 檔</div>
          <div>接近觀察：<strong>{watch_count}</strong> 檔</div>
          <div>最後更新：<strong>{updated_at or "未標示"}</strong></div>
        </div>
        <p>每日網頁版：<a href="{site_url}">{site_url}</a></p>
        <p>以下為 candidate_score 排名前 15 的股票：</p>
        {_build_table(df)}
        <p style="color:#57606a;font-size:12px;margin-top:20px;">
          本工具只做篩選與整理，不構成投資建議。完整 CSV / Excel 可從網頁下載。
        </p>
      </body>
    </html>
    """
    return subject, html


def main() -> int:
    smtp_host = _env("SMTP_HOST")
    smtp_port = _env_int("SMTP_PORT", 587)
    smtp_username = _env("SMTP_USERNAME")
    smtp_password = _env("SMTP_PASSWORD")
    smtp_from = _env("SMTP_FROM", smtp_username)
    recipients = _split_recipients(_env("EMAIL_TO", DEFAULT_RECIPIENTS))
    site_url = _env("CANDY_STOCK_SITE_URL", DEFAULT_SITE_URL)

    if not all([smtp_host, smtp_username, smtp_password, smtp_from]) or not recipients:
        print("Email notification skipped: SMTP secrets or recipients are not configured.")
        return 0

    subject, html = _build_message(Path("output/screening_result.csv"), site_url)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = ", ".join(recipients)
    message.set_content("請使用支援 HTML 的郵件用戶端查看今日台股候選清單。")
    message.add_alternative(html, subtype="html")

    try:
        context = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as smtp:
                smtp.login(smtp_username, smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(smtp_username, smtp_password)
                smtp.send_message(message)
    except Exception as exc:
        print(f"Email notification failed but screener output is kept: {exc}")
        return 0

    print(f"Email notification sent to {', '.join(recipients)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
