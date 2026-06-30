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
    
    # 建立表格
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
    cat_str = ",".join(categories) if isinstance(categories, list) else categories
    kw_str = ",".join(keywords) if isinstance(keywords, list) else keywords
    
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
        print(f"Insert error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def query_articles(date_filter=None):
    conn = get_connection()
    cur = conn.cursor()
    query = "SELECT * FROM articles"
    params = []
    if date_filter:
        query += " WHERE date = %s" if DB_URL else " WHERE date = ?"
        params.append(date_filter)
    cur.execute(query, params)
    rows = cur.fetchall()
    results = [dict(row) for row in rows]
    cur.close()
    conn.close()
    return results

def get_stats():
    """統計各類別文章數量"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT categories, COUNT(*) as count FROM articles GROUP BY categories")
    rows = cur.fetchall()
    
    # 處理回傳格式差異
    if DB_URL:
        stats = {row['categories']: row['count'] for row in rows}
    else:
        stats = {row['categories']: row['count'] for row in rows}
        
    cur.close()
    conn.close()
    return stats
