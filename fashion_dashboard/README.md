# 每日時尚與紡織產業新聞情報看板

## 專案結構
```
fashion_dashboard/
├── app.py            # FastAPI 後端主程式（API + 靜態網頁掛載）
├── database.py       # SQLite 資料庫初始化與存取
├── classifier.py      # 核心分類邏輯（LLM 分類 + 離線規則式備援）
├── rss_fetcher.py     # 方案 B：RSS 自動抓取腳本
├── seed_demo.py        # 範例資料填充腳本（測試用）
├── requirements.txt
└── static/
    └── index.html     # 前端（Tailwind + Chart.js + Vanilla JS）
```

## 快速啟動

```bash
cd fashion_dashboard
pip install -r requirements.txt

# (可選) 設定 LLM API Key，沒有設定的話會自動降級用關鍵字規則式分類，仍可正常跑通整套系統
export ANTHROPIC_API_KEY="sk-ant-..."

uvicorn app:app --reload --port 8000
```

打開瀏覽器訪問 `http://127.0.0.1:8000` 即可看到看板。

### 先塞入測試資料（強烈建議第一次跑先做這步）
另開一個終端機視窗：
```bash
python seed_demo.py
```
這會丟 6 篇範例新聞進後端，並自動跑分類，馬上就能看到完整效果。

### 接上真正的 RSS 來源
編輯 `rss_fetcher.py` 裡的 `RSS_FEEDS` 字典，填入你實際要追蹤的 RSS 網址，然後：
```bash
python rss_fetcher.py
```
建議搭配 cron（Linux/Mac）或工作排程器（Windows）每天定時執行，例如每天早上 8 點：
```cron
0 8 * * * cd /path/to/fashion_dashboard && /usr/bin/python3 rss_fetcher.py >> fetch.log 2>&1
```

## 分類邏輯說明
`classifier.py` 中的 `classify_article(title, summary)` 是統一入口：
- 若有設定 `ANTHROPIC_API_KEY`：呼叫 Claude API，依 5 大分類描述 + 文章內容，回傳多選分類標籤與一句話摘要（JSON 格式）。
- 若沒有設定 API Key：自動降級為關鍵字規則比對（離線可跑，方便先用免費方式測試整套流程，之後再接上真正 LLM）。

若想換成 OpenAI 或其他 LLM 供應商，只需要修改 `classify_with_llm()` 內部的 API 呼叫部分，保持回傳格式 `{"categories": [...], "summary": "..."}` 不變即可，其他程式碼都不用動。

## 資料庫欄位
SQLite 表 `articles`：
| 欄位 | 說明 |
|---|---|
| date | 文章發布日期 YYYY-MM-DD |
| source | 媒體名稱 |
| title | 文章標題 |
| url | 原文連結（唯一值，避免重複抓取同一篇） |
| summary | AI 生成的精簡摘要 |
| categories | 逗號分隔字串，例如 `Trends & Aesthetics,Marketing & Collaborations` |

## API 一覽
| Method | 路徑 | 說明 |
|---|---|---|
| GET | `/api/articles?date=&categories=` | 取得文章列表，可用日期與分類（逗號分隔，多選 OR 邏輯）篩選 |
| GET | `/api/stats?date=` | 取得今日總篇數與各分類統計，前端圖表用 |
| GET | `/api/categories` | 取得系統 5 大分類清單 |
| POST | `/api/articles` | 新增一篇文章（後端自動分類 + 摘要） |

## 前端設計重點
- 配色：米灰底色 `#F7F6F4`、深炭黑文字 `#2B2A28`，細線分隔 `#DEDAD3`，無高飽和亮色。
- 分類標籤用「深淺不同的灰階色塊」區分 5 大分類，越核心的商業類用越深色，越輕量的行銷類用越淺色，符合「軟極簡」質感。
- 頂部即時統計甜甜圈圖（Chart.js）+ 圖例，呈現今日分類佔比。
- 篩選器支援日期單選 + 分類多選（chips 點擊切換）。
- 卡片點擊標題直接跳轉原文連結（新分頁開啟）。

## 部署建議
- 小規模／個人使用：直接在自己的伺服器或 NAS 上跑 `uvicorn` + cron 排程即可。
- 正式環境：建議加上 `gunicorn -k uvicorn.workers.UvicornWorker app:app` 多進程運行，並用 Nginx 反向代理 + HTTPS。
- 資料庫量大後，建議把 SQLite 換成 PostgreSQL（`database.py` 的 SQL 介面可直接沿用，只需更換連線方式）。
