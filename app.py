from typing import Optional, List
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
from contextlib import asynccontextmanager

from database import init_db, insert_article, query_articles, get_stats
from classifier import classify_article, CATEGORIES
import seed_demo  # 確保與你的 seed_demo.py 檔案名稱一致

# --- 1. 定義生命週期管理 (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 伺服器啟動時：初始化 DB 並同步關鍵詞
    init_db()
    print("正在啟動：正在檢查與更新資料庫關鍵詞...")
    try:
        # 呼叫 seed_demo.py 裡的函數
        # 請確認 seed_demo.py 內包含 def run_seed():
        seed_demo.run_seed() 
        print("資料庫關鍵詞檢查與更新完成！")
    except Exception as e:
        print(f"資料庫更新失敗: {e}")
    yield  # 應用程式在此處開始運行
    # 伺服器關閉時（這裡可以留空）

# --- 2. 初始化 FastAPI 並掛載 lifespan ---
app = FastAPI(title="每日時尚與紡織產業新聞情報看板", lifespan=lifespan)

# --- 3. 設定 CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. 資料模型 ---
class ArticleIn(BaseModel):
    date: Optional[str] = None 
    source: str
    title: str
    url: str
    raw_summary: Optional[str] = ""

# --- 5. 路由定義 ---
@app.get("/api/categories")
def get_categories():
    return {"categories": CATEGORIES}

@app.get("/api/articles")
def get_articles(
    date: Optional[str] = Query(None),
    categories: Optional[str] = Query(None),
):
    cat_list = categories.split(",") if categories else None
    return {"articles": query_articles(date_filter=date, category_filter=cat_list)}

@app.get("/api/stats")
def get_stats_api(date: Optional[str] = Query(None)):
    return get_stats(date_filter=date)

@app.post("/api/articles")
def create_article(item: ArticleIn):
    date = item.date or datetime.date.today().isoformat()
    result = classify_article(item.title, item.raw_summary or "")
    inserted = insert_article(
        date=date,
        source=item.source,
        title=item.title,
        url=item.url,
        summary=result["summary"],
        categories=result["categories"],
        keywords=result.get("keywords", []),
    )
    return {
        "inserted": inserted,
        "categories": result["categories"],
        "summary": result["summary"],
        "keywords": result.get("keywords", []),
    }

# --- 6. 前端靜態檔案 ---
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")
