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
- GitHub Pages 會自動部署每日 HTML 頁面，網址預設為 `https://scoppenlin.github.io/CandyTWStock/`。

若篩選筆數是 0，代表程式有成功輸出，但目前股票清單與參數沒有股票符合條件；可先放寬 `config.py` 裡的 RSI / KD / 放量倍數條件，或增加 `data/stock_list.csv` 股票清單。

排程預設為台灣時間週一到週五 18:00 自動執行。若第一次使用 GitHub Pages，請到 repo 的 `Settings` -> `Pages`，確認 Build and deployment 的 Source 使用 `GitHub Actions`。

### 每日 Email 通知

GitHub Actions 跑完後會嘗試寄出每日候選清單摘要到：

- `huiju999@yahoo.com.tw`
- `scoppen.lin@gmail.com`

請到 repo 的 `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret` 新增以下 secrets：

| Secret | 說明 |
| --- | --- |
| `SMTP_HOST` | SMTP 主機，例如 Gmail 使用 `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 連接埠，通常是 `587`，若使用 SSL 可填 `465` |
| `SMTP_USERNAME` | 寄件信箱帳號 |
| `SMTP_PASSWORD` | SMTP 密碼或應用程式密碼 |
| `SMTP_FROM` | 寄件人信箱，通常與 `SMTP_USERNAME` 相同 |

若使用 Gmail 寄信，建議在 Google 帳號啟用兩步驟驗證後建立「應用程式密碼」，再把該密碼填入 `SMTP_PASSWORD`。若 secrets 尚未設定，workflow 仍會正常產生 CSV / Excel / HTML，只會略過寄信。

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
- [output/strict_candidates.xlsx](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/output/strict_candidates.xlsx)
- [output/watchlist_candidates.xlsx](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/output/watchlist_candidates.xlsx)
- [output/candidates.html](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/output/candidates.html)
- [logs/error_log.csv](/Users/LinScoppen/Documents/VS%20Projects/CandyStock/logs/error_log.csv)

單一股票抓不到股價資料時會略過並寫入錯誤紀錄。法人資料抓取失敗時，仍會輸出技術面篩選結果，法人欄位補 0。

## 輸出欄位說明

輸出表格包含：

- 股票代號、股票名稱、市場
- 收盤價、MA20、是否站上 MA20
- K 值、D 值、RSI
- Volume_MA5、Volume_MA20、Volume_MA40、放量倍數
- MACD_DIF、MACD_Signal、MACD_Histogram、前 1 日 / 前 2 日 Histogram
- MACD_綠柱趨緩接近翻紅，僅做參考標註，不作為硬性篩選條件
- candidate_level、candidate_score，以及 KD / RSI / 放量 / 法人買超檢查欄位
- 外資、投信、自營商、三大法人近 1 日 / 5 日 / 20 日買賣超張數
- 最後更新日期

排序邏輯：

1. candidate_score 由高到低
2. 放量倍數由高到低
3. 三大法人近 5 日合計買賣超張數由高到低
4. 投信近 5 日買賣超張數由高到低
5. RSI 由低到高

## 候選名單邏輯

`candidate_level = 符合` 代表完全符合嚴格條件：收盤價低於 300、KD 介於 30 到 50、K > D、RSI 介於 30 到 50、Volume_MA5 同時大於 Volume_MA20 的 1.5 倍與 Volume_MA40 的 1.3 倍。

`candidate_level = 接近` 代表符合多數觀察條件：價格、較寬的 KD / RSI 區間、較低的放量門檻、MACD 綠柱縮短接近翻紅、或法人 / 投信近 5 日買超。門檻可在 `config.py` 的 `watch_*` 參數調整。

`candidate_score` 滿分 100 分：KD 20、RSI 20、Volume_MA5 / Volume_MA20 20、Volume_MA5 / Volume_MA40 10、MACD 10、三大法人近 5 日買超 10、投信近 5 日買超 10。

## HTML 每日觀察頁

執行後會產生 `output/candidates.html`，包含摘要卡、嚴格符合名單、接近觀察名單，以及適合每日快速掃描的主要欄位。GitHub Actions 跑完後也會自動把這個 HTML 檔 commit 回 repo。

GitHub Pages 會把 `output/candidates.html` 發布成 `index.html`，並把 CSV / Excel 放在網頁的 `downloads/` 路徑下，方便在任何裝置開啟或下載。

## 股票清單更新

預設 `auto_refresh_stock_list = True`，執行時會優先從 TWSE OpenAPI 更新上市與上櫃公司基本資料，並覆寫 `data/stock_list.csv`。若官方資料抓取失敗，會退回使用本機 CSV。

## 可能限制

- yfinance 的台股資料可能不完整，部分股票可能沒有資料或延遲。
- TWSE / TPEx 法人資料可能遇到假日、資料延遲、網站格式調整或暫時阻擋。
- TPEx 公開資料不同端點可能有股數 / 張數單位差異，程式會嘗試轉成張，但仍建議抽樣核對。
- `data/stock_list.csv` 目前是 MVP 手動清單，正式使用建議改接 TWSE / TPEx 股票清單或自建資料庫。
- 本工具只做篩選，不構成投資建議。
