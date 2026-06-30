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

    # === 以下為新增來源（依使用者提供的分類清單）===

    # -- 1. 商業動態 (Corporate & Market) --
    "Retail Dive": "https://www.retaildive.com/feeds/news/",
    # Fashion Network 官方條款明確禁止「商業/專業用途」使用其 RSS（包含本系統這種自動彙整用途），
    # 故不直接訂閱其官方 RSS，改用 Google News 變通取得公開可索引的報導標題，較不踩法律風險。
    "Fashion Network (Google News)": "https://news.google.com/rss/search?q=site:fashionnetwork.com&hl=zh-TW&gl=TW",

    # -- 2. 流行美學 (Trends & Aesthetics) --
    "Dezeen": "https://www.dezeen.com/feed/",
    "It's Nice That (Google News)": "https://news.google.com/rss/search?q=site:itsnicethat.com&hl=en-US&gl=US",
    "Core77": "https://www.core77.com/blog/rss.xml",
    "Designboom": "https://www.designboom.com/feed/",
    "Interior Design (Google News)": "https://news.google.com/rss/search?q=site:interiordesign.net&hl=en-US&gl=US",
    "Surface Magazine (Google News)": "https://news.google.com/rss/search?q=site:surfacemag.com&hl=en-US&gl=US",
    "Metropolis Magazine (Google News)": "https://news.google.com/rss/search?q=site:metropolismag.com&hl=en-US&gl=US",
    # PV市集展屬於貿易展覽會官網，幾乎不提供 RSS，用 Google News 變通取得相關報導
    "PV市集展 Première Vision (Google News)": "https://news.google.com/rss/search?q=%22Premiere+Vision%22&hl=zh-TW&gl=TW",

    # -- 3. 供應鏈與紡織技術 (Supply Chain & Textile Tech) --
    # MILANO UNICA 同樣是展會官網，無官方 RSS，用 Google News 變通
    "MILANO UNICA (Google News)": "https://news.google.com/rss/search?q=%22Milano+Unica%22&hl=zh-TW&gl=TW",
    "Innovation in Textiles (Google News)": "https://news.google.com/rss/search?q=site:innovationintextiles.com&hl=en-US&gl=US",

    # -- 4. 行銷聯名 (Marketing & Collaborations) --
    "Marketing Dive": "https://www.marketingdive.com/feeds/news/",
    # SPINEXPO 是展會網站，Communication 分區無獨立 RSS，用 Google News 變通
    "SPINEXPO Communication (Google News)": "https://news.google.com/rss/search?q=%22SPINEXPO%22&hl=zh-TW&gl=TW",

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


import os

# 後端 FastAPI 服務位址。
# 重要修正：原本寫死 "http://127.0.0.1:8000"（本機位址），
# 導致你在自己電腦執行這支腳本時，抓到的新聞其實是送到「你自己電腦的本機伺服器」，
# 完全沒有送進 Railway 上的正式資料庫，跟你在瀏覽器看到的正式網站是兩個獨立的東西。
#
# 現在改成預設指向正式 Railway 網址；如果你之後想切換回本機測試，
# 可以用環境變數覆寫，例如本機測試時執行：
#   set API_BASE=http://127.0.0.1:8000   (Windows)
#   export API_BASE=http://127.0.0.1:8000 (Mac/Linux)
API_BASE = os.environ.get("API_BASE", "https://fashion-newsboard-production.up.railway.app")


def parse_date(entry) -> str:
    """
    回傳這篇文章要被歸到看板上的「日期」。

    設計考量：這個系統定位是「每日新聞情報看板」，篩選器的「日期」應該代表
    「我哪一天抓到了這些新聞」，而不是文章本身原始的發布時間。
    因為很多 RSS / Google News 來源裡混雜了大量數月、甚至數年前的舊文章
    （原始發布日期落在過去），如果用原始發布日期儲存，會導致使用者選某一天時
    幾乎抓不到任何資料 —— 因為文章原始日期幾乎不會剛好落在使用者選的那天。

    所以這裡固定回傳「程式執行（抓取）當天」的日期，讓每次跑 rss_fetcher.py
    抓到的所有文章，都統一歸在當天，篩選器才會跟「哪天抓的」這個直覺一致。
    """
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
            date = parse_date(entry)  # = 今天（抓取當天），詳見函式內說明

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
