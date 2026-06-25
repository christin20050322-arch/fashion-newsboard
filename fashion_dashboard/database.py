"""
database.py
------------
SQLite 資料庫初始化與基本存取函式。
"""
import sqlite3
from contextlib import contextmanager

DB_PATH = "fashion_news.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,            -- 文章發布日期 YYYY-MM-DD
    source TEXT NOT NULL,          -- 媒體名稱
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,      -- 用 URL 避免重複抓取
    summary TEXT,                  -- AI 核心摘要
    categories TEXT,               -- 以逗號分隔儲存多分類，例如 "Trends,Sustainability"
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(SCHEMA)


def insert_article(date, source, title, url, summary, categories: list[str]):
    """categories 傳入 list，內部轉成逗號分隔字串儲存"""
    cat_str = ",".join(categories)
    with get_conn() as conn:
        try:
            conn.execute(
                """INSERT INTO articles (date, source, title, url, summary, categories)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (date, source, title, url, summary, cat_str),
            )
            return True
        except sqlite3.IntegrityError:
            # URL 已存在，視為已抓取過，跳過
            return False


def query_articles(date_filter=None, category_filter: list[str] | None = None):
    """
    date_filter: "YYYY-MM-DD" 或 None（不篩選）
    category_filter: ["Trends", "Sustainability"] 或 None（不篩選，OR 邏輯：符合任一分類即顯示）
    """
    sql = "SELECT * FROM articles WHERE 1=1"
    params = []
    if date_filter:
        sql += " AND date = ?"
        params.append(date_filter)
    sql += " ORDER BY date DESC, id DESC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    results = []
    for r in rows:
        cats = r["categories"].split(",") if r["categories"] else []
        if category_filter:
            if not any(c in cats for c in category_filter):
                continue
        results.append({
            "id": r["id"],
            "date": r["date"],
            "source": r["source"],
            "title": r["title"],
            "url": r["url"],
            "summary": r["summary"],
            "categories": cats,
        })
    return results


def get_stats(date_filter=None):
    """回傳今日總篇數，以及各分類篇數統計（用於前端圖表）"""
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
