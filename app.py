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

# --- 1. 定義生命週期管理 (Lifespan) ---
# 注意：正式環境的 lifespan 只應該做「初始化資料庫結構」，
# 不該呼叫 seed_demo.run_seed()。
# 之前的版本每次伺服器啟動（=每次 Railway 重新部署）都會塞入示範資料，
# 這在概念上是錯的：示範資料只該在「本機第一次測試」時手動執行一次
# （python seed_demo.py），不該綁進正式網站的啟動流程。
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

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
