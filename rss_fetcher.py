"""
rss_fetcher.py
---------------
方案 B：定時 RSS 抓取腳本。

用法：
    pip install feedparser requests
    python rss_fetcher.py

可搭配 cron / Windows 排程器每天執行，例如每天早上 8:00：
    0 8 * * * /usr/bin/python3 /path/to/rss_fetcher.py >> /path/to/fetch.log 2>&1

腳本邏輯：
1. 走訪設定好的 RSS Feed 清單。
2. 解析每篇文章的標題、連結、發布日期、摘要(若RSS有附)。
3. 呼叫後端 /api/articles，後端會自動做分類 + AI 摘要 + 寫入資料庫。
   （若不想透過 API，也可以改成直接 import database/classifier 在本機處理，註解處有範例）
"""
import feedparser
import requests
import datetime
import time

# ---------------------------------------------------------------------------
# 1. 設定要追蹤的 RSS 來源（請依實際可用 Feed 網址調整）
# ---------------------------------------------------------------------------
RSS_FEEDS = {
    # --- 官方確認有提供 RSS 的來源 ---
    "Business of Fashion": "https://www.businessoffashion.com/feed/",
    "WWD": "https://wwd.com/feed/",
    "FashionUnited": "https://fashionunited.com/rss",
    "Fibre2Fashion - 產業綜合": "https://feeds.feedburner.com/fibre2fashion",
    "Fibre2Fashion - 紡織新聞": "https://feeds.feedburner.com/fibre2fashion/textile-news",
    "Fibre2Fashion - 服裝新聞": "https://feeds.feedburner.com/fibre2fashion/apparelnews",
    "Fibre2Fashion - 時尚新聞": "https://feeds.feedburner.com/fibre2fashion/fashion-news",
    "Just Style": "https://www.just-style.com/feed/",

    # --- 沒有官方 RSS 的來源，透過 Google News 包成 RSS 變通取得 ---
    "Vogue Business (Google News)":      "https://news.google.com/rss/search?q=site:voguebusiness.com&hl=zh-TW&gl=TW",
    "Sourcing Journal (Google News)":    "https://news.google.com/rss/search?q=site:sourcingjournal.com&hl=en-US&gl=US",
    "Hypebeast (Google News)":           "https://news.google.com/rss/search?q=site:hypebeast.com&hl=zh-TW&gl=TW",
    "Highsnobiety (Google News)":        "https://news.google.com/rss/search?q=site:highsnobiety.com&hl=en-US&gl=US",
    "Textile World (Google News)":       "https://news.google.com/rss/search?q=site:textileworld.com&hl=en-US&gl=US",
    "Apparel Resources (Google News)":   "https://news.google.com/rss/search?q=site:apparelresources.com&hl=en-US&gl=US",
    "Knitting Industry (Google News)":   "https://news.google.com/rss/search?q=site:knittingindustry.com&hl=en-US&gl=US",
    "CTNET 中國紡織服裝服飾網 (Google News)": "https://news.google.com/rss/search?q=site:ctnet.com.cn&hl=zh-TW&gl=TW",
    "華衣網 (Google News)":               "https://news.google.com/rss/search?q=site:ef360.com&hl=zh-TW&gl=TW",
    "Tnet 全球紡織資訊網 (Google News)":   "https://news.google.com/rss/search?q=site:tnet.org.tw&hl=zh-TW&gl=TW",

    # 提示：上面 Google News 變通方案不保證每個站點都能搜到結果，
    # 如果某一個來源一直抓不到文章，可以把該行刪除或註解掉（在行首加 # ）即可，不影響其他來源運作。
}

API_BASE = "http://127.0.0.1:8000"  # 後端 FastAPI 服務位址


def parse_date(entry) -> str:
    """嘗試從 RSS entry 解析發布日期，失敗則用今天"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime.datetime(*entry.published_parsed[:6])
        return dt.date().isoformat()
    return datetime.date.today().isoformat()


def fetch_and_push():
    total_new = 0
    for source_name, feed_url in RSS_FEEDS.items():
        print(f"[INFO] 抓取來源：{source_name} ({feed_url})")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[ERROR] 無法抓取 {source_name}：{e}")
            continue

        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            url = getattr(entry, "link", "").strip()
            raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            date = parse_date(entry)

            if not title or not url:
                continue

            payload = {
                "date": date,
                "source": source_name,
                "title": title,
                "url": url,
                "raw_summary": raw_summary,
            }
            try:
                resp = requests.post(f"{API_BASE}/api/articles", json=payload, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                if data.get("inserted"):
                    total_new += 1
                    print(f"  -> 新增：{title[:50]}... 分類：{data['categories']}")
            except Exception as e:
                print(f"[ERROR] 推送文章失敗：{title[:30]}... -> {e}")

            time.sleep(0.3)  # 避免過快打 API / LLM 速率限制

    print(f"[DONE] 本次抓取完成，新增 {total_new} 篇文章。")


if __name__ == "__main__":
    fetch_and_push()
