import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

# 獲取環境變數
DB_URL = os.environ.get("DATABASE_URL")

def get_connection():
    """自動判斷模式：若有 DB_URL 則連 PostgreSQL，否則用 SQLite"""
    if DB_URL:
        return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    else:
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
    """查詢文章"""
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

def get_stats(date_filter=None): # 務必加上 date_filter=None
    """統計各分類文章數量"""
    conn = get_connection()
    cur = conn.cursor()
    
    # 若有日期篩選，加入 WHERE 條件
    query = "SELECT categories, COUNT(*) as count FROM articles"
    params = []
    if date_filter:
        query += " WHERE date = %s" if DB_URL else " WHERE date = ?"
        params.append(date_filter)
    query += " GROUP BY categories"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    stats = {}
    for row in rows:
        r = dict(row)
        # 處理多分類字串拆解
        cat_field = r.get('categories', '')
        if cat_field:
            categories = cat_field.split(',')
            for cat in categories:
                cat = cat.strip()
                stats[cat] = stats.get(cat, 0) + r['count']
        
    cur.close()
    conn.close()
    return stats
