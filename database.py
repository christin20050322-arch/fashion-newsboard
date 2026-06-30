import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

# 獲取環境變數 (Railway 會自動提供 DATABASE_URL)
DB_URL = os.environ.get("DATABASE_URL")

def get_connection():
    """自動判斷模式：若有 DB_URL 則連 PostgreSQL，否則用 SQLite"""
    if DB_URL:
        # PostgreSQL 模式 (Railway)
        return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    else:
        # SQLite 模式 (本地)
        conn = sqlite3.connect("fashion_news.db")
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """初始化資料庫表結構"""
    conn = get_connection()
    cur = conn.cursor()
    
    # 針對兩者差異使用 SQL
    if DB_URL:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            date TEXT,
            source TEXT,
            title TEXT UNIQUE,
            url TEXT,
            summary TEXT,
            categories TEXT,
            keywords TEXT
        );
        """
    else:
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            source TEXT,
            title TEXT UNIQUE,
            url TEXT,
            summary TEXT,
            categories TEXT,
            keywords TEXT
        );
        """
    
    cur.execute(create_table_sql)
    conn.commit()
    cur.close()
    conn.close()

def insert_article(date, source, title, url, summary, categories, keywords):
    """寫入文章，自動處理重複"""
    conn = get_connection()
    cur = conn.cursor()
    
    cat_str = ",".join(categories)
    kw_str = ",".join(keywords)
    
    try:
        if DB_URL:
            cur.execute("""
                INSERT INTO articles (date, source, title, url, summary, categories, keywords)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (title) DO NOTHING
            """, (date, source, title, url, summary, cat_str, kw_str))
        else:
            cur.execute("""
                INSERT OR IGNORE INTO articles (date, source, title, url, summary, categories, keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date, source, title, url, summary, cat_str, kw_str))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Database insert error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def query_articles(date_filter=None, category_filter=None):
    """查詢文章 (支援篩選)"""
    conn = get_connection()
    cur = conn.cursor()
    
    query = "SELECT * FROM articles WHERE 1=1"
    params = []
    
    if date_filter:
        query += " AND date = ?" if not DB_URL else " AND date = %s"
        params.append(date_filter)
        
    cur.execute(query, params)
    rows = cur.fetchall()
    
    # 將 dict 或 Row 轉為一般列表輸出
    results = [dict(row) for row in rows]
    
    cur.close()
    conn.close()
    return results

def get_stats(date_filter=None):
    """統計各分類文章數量"""
    conn = get_connection()
    cur = conn.cursor()
    
    query = "SELECT categories, COUNT(*) as count FROM articles GROUP BY categories"
    cur.execute(query)
    rows = cur.fetchall()
    
    stats = {dict(row)["categories"]: dict(row)["count"] for row in rows}
    
    cur.close()
    conn.close()
    return stats
