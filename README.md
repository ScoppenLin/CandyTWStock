# 台股低位轉強放量選股器 MVP

這是一個 Python 版台股篩選工具，用來找出股價相對不高、KD / RSI 位於 30 到 50 低位轉強區間、近期成交量明顯放大，並同步觀察三大法人是否開始布局的候選股票。

本工具只做資料篩選與整理，不構成任何投資建議。

## 安裝方式

建議使用 Python 3.10 以上版本。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 如何執行

```bash
python3 screener.py
```

若想指定另一份股票清單：

```bash
python3 screener.py --stock-list data/stock_list.csv
```

若想啟用 `Close > MA20` 條件：

```bash
python3 screener.py --require-close-above-ma20
```

## 在 GitHub Actions 執行

到 GitHub repo 的 `Actions` 頁面，選擇 `Run Taiwan Stock Screener`，按 `Run workflow`。

執行完成後有兩個地方可以看結果：

- Actions run 頁面的 Summary 會顯示篩選筆數與近期錯誤。
- Repo 內會自動更新 `output/screening_result.csv`、`output/screening_result.xlsx`、`logs/error_log.csv`。

若篩選筆數是 0，代表程式有成功輸出，但目前股票清單與參數沒有股票符合條件；可先放寬 `config.py` 裡的 RSI / KD / 放量倍數條件，或增加 `data/stock_list.csv` 股票清單。

## 如何調整參數

所有主要參數集中在 [config.py](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/config.py) 的 `CONFIG` 區塊，例如：

- `price_limit`: 最新收盤價上限，預設 300。
- `kd_min` / `kd_max`: K、D 值篩選區間，預設 30 到 50。
- `rsi_min` / `rsi_max`: RSI 篩選區間，預設 30 到 50。
- `volume_mid_multiplier`: `Volume_MA5 > Volume_MA20 * multiplier` 的倍數。
- `volume_long_multiplier`: `Volume_MA5 > Volume_MA40 * multiplier` 的倍數。
- `require_close_above_ma20`: 是否要求收盤價站上 MA20，預設 `False`。
- `exclude_etf` / `exclude_warrant` / `exclude_special_stock` / `exclude_ky`: 股票清單排除條件。

## 股票清單格式

手動維護檔案位於 [data/stock_list.csv](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/data/stock_list.csv)，欄位如下：

```csv
symbol,name,market
2330,台積電,上市
6488,環球晶,上櫃
```

`market` 只接受 `上市` 或 `上櫃`。上市股票會用 yfinance ticker `2330.TW`，上櫃股票會用 `6488.TWO`。

## 輸出檔案

執行後會產生：

- [output/screening_result.csv](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/output/screening_result.csv)
- [output/screening_result.xlsx](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/output/screening_result.xlsx)
- [logs/error_log.csv](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/logs/error_log.csv)

單一股票抓不到股價資料時會略過並寫入錯誤紀錄。法人資料抓取失敗時，仍會輸出技術面篩選結果，法人欄位補 0。

## 輸出欄位說明

輸出表格包含：

- 股票代號、股票名稱、市場
- 收盤價、MA20、是否站上 MA20
- K 值、D 值、RSI
- Volume_MA5、Volume_MA20、Volume_MA40、放量倍數
- 外資、投信、自營商、三大法人近 1 日 / 5 日 / 20 日買賣超張數
- 最後更新日期

排序邏輯：

1. 放量倍數由高到低
2. 三大法人近 5 日合計買賣超張數由高到低
3. 投信近 5 日買賣超張數由高到低
4. RSI 由低到高

## 可能限制

- yfinance 的台股資料可能不完整，部分股票可能沒有資料或延遲。
- TWSE / TPEx 法人資料可能遇到假日、資料延遲、網站格式調整或暫時阻擋。
- TPEx 公開資料不同端點可能有股數 / 張數單位差異，程式會嘗試轉成張，但仍建議抽樣核對。
- `data/stock_list.csv` 目前是 MVP 手動清單，正式使用建議改接 TWSE / TPEx 股票清單或自建資料庫。
- 本工具只做篩選，不構成投資建議。
