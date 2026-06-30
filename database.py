"""
database.py
------------
資料庫初始化與基本存取函式。

雙模式設計：
- 有 DATABASE_URL 環境變數（Railway 加裝 PostgreSQL 後會自動注入）-> 用 PostgreSQL，資料永久保存
- 沒有 DATABASE_URL（例如本機測試）-> 自動退回 SQLite 檔案

修正紀錄（這次排查到的致命 bug）：
1. query_articles() 補回 category_filter 參數 —— 之前少了這個參數，
   只要前端打 /api/articles 就會直接丟出 TypeError，整個 API 壞掉，
   這是「完全沒有顯示新聞」的直接原因。
2. query_articles() 回傳時把 categories / keywords 從逗號分隔字串
   正確切成 list，否則前端會把字串當陣列逐字元拆解，畫面全部跑版。
3. get_stats() 改回回傳 {"total": ..., "by_category": {...5大分類...}}
   這個前端期待的格式，而不是直接回傳扁平的分類計數字典。
4. insert_article 的唯一性判斷改回以 url 為準（而不是 title），
   避免不同媒體剛好標題相同時被誤判成重複而漏存。
5. insert_article 改用「實際是否真的新增」判斷回傳值
   （用 cursor.rowcount / RETURNING），避免 rss_fetcher.py 的
   「新增 N 篇」統計數字失真。
"""
import os
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Railway／Heroku 早期版本給的網址有時是 "postgres://" 開頭，
    # 但 psycopg2 嚴格要求要是 "postgresql://"，這裡自動修正避免連線失敗。
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    import sqlite3
    SQLITE_PATH = "fashion_news.db"


def get_connection():
    """自動判斷模式：若有 DATABASE_URL 則連 PostgreSQL，否則用 SQLite"""
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """初始化資料庫表結構（含相容舊資料庫的欄位補齊）"""
    conn = get_connection()
    cur = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                summary TEXT,
                categories TEXT,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
        # 相容檢查：舊資料庫如果是用更早期 schema 建的，補上缺少的欄位
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'articles'")
        cols = [row["column_name"] for row in cur.fetchall()]
        if "keywords" not in cols:
            cur.execute("ALTER TABLE articles ADD COLUMN keywords TEXT")
        if "url" not in cols:
            cur.execute("ALTER TABLE articles ADD COLUMN url TEXT")
        conn.commit()
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                summary TEXT,
                categories TEXT,
                keywords TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        cols = [row[1] for row in cur.execute("PRAGMA table_info(articles)").fetchall()]
        if "keywords" not in cols:
            cur.execute("ALTER TABLE articles ADD COLUMN keywords TEXT")
            conn.commit()

    cur.close()
    conn.close()


def insert_article(date, source, title, url, summary, categories, keywords=None):
    """
    寫入文章，以 url 當作唯一性判斷依據（不同媒體標題剛好相同也不會被誤判重複）。
    回傳 True 代表「真的新增成功」；回傳 False 代表這個 url 已存在、本次跳過。
    """
    conn = get_connection()
    cur = conn.cursor()
    cat_str = ",".join(categories) if isinstance(categories, list) else (categories or "")
    kw_str = ",".join(keywords) if isinstance(keywords, list) else (keywords or "")

    try:
        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO articles (date, source, title, url, summary, categories, keywords)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                RETURNING id
            """, (date, source, title, url, summary, cat_str, kw_str))
            row = cur.fetchone()
            conn.commit()
            return row is not None
        else:
            cur.execute("""
                INSERT OR IGNORE INTO articles (date, source, title, url, summary, categories, keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date, source, title, url, summary, cat_str, kw_str))
            conn.commit()
            return cur.rowcount > 0  # rowcount=0 代表 url 已存在、被 IGNORE 跳過
    except Exception as e:
        print(f"[ERROR] insert_article 失敗：{e}")
        return False
    finally:
        cur.close()
        conn.close()


def query_articles(date_filter=None, category_filter=None):
    """
    date_filter: "YYYY-MM-DD" 或 None（不篩選）
    category_filter: ["Trends & Aesthetics", ...] 或 None（不篩選，OR 邏輯：符合任一分類即顯示）

    回傳格式固定為前端期待的樣子：
    categories / keywords 一定是 list（不是逗號字串）。
    """
    conn = get_connection()
    cur = conn.cursor()

    query = "SELECT * FROM articles WHERE 1=1"
    params = []
    if date_filter:
        query += " AND date = %s" if USE_POSTGRES else " AND date = ?"
        params.append(date_filter)
    query += " ORDER BY date DESC, id DESC"

    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)
        cats = r["categories"].split(",") if r.get("categories") else []
        if category_filter:
            if not any(c in cats for c in category_filter):
                continue
        kws = r["keywords"].split(",") if r.get("keywords") else []
        results.append({
            "id": r["id"],
            "date": r["date"],
            "source": r["source"],
            "title": r["title"],
            "url": r["url"],
            "summary": r["summary"],
            "categories": cats,
            "keywords": kws,
        })
    return results


def get_stats(date_filter=None):
    """
    回傳前端期待的格式：
    { "total": 篇數, "by_category": { "Corporate & Market": 5, ... 5大分類都會有key，沒有就是0 } }
    """
    articles = query_articles(date_filter=date_filter)
    total = len(articles)
    cat_counts = {
        "Corporate & Market": 0,
        "Trends & Aesthetics": 0,
        "Supply Chain & Textile Tech": 0,
        "Sustainability & ESG": 0,
        "Marketing & Collaborations": 0,
    }
    for a in articles:
        for c in a["categories"]:
            if c in cat_counts:
                cat_counts[c] += 1
    return {"total": total, "by_category": cat_counts}
