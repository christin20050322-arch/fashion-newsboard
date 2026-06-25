"""
app.py
-------
FastAPI 後端主程式。

啟動方式：
    pip install -r requirements.txt
    uvicorn app:app --reload --port 8000

前端會呼叫：
    GET /api/articles?date=2026-06-25&categories=Trends%20%26%20Aesthetics,Sustainability%20%26%20ESG
    GET /api/stats?date=2026-06-25
    POST /api/articles  (手動新增一篇文章，內部會自動呼叫分類器)
"""
from typing import Optional, List
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime

from database import init_db, insert_article, query_articles, get_stats
from classifier import classify_article, CATEGORIES

app = FastAPI(title="每日時尚與紡織產業新聞情報看板")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class ArticleIn(BaseModel):
    date: Optional[str] = None  # 不填則用今天日期
    source: str
    title: str
    url: str
    raw_summary: Optional[str] = ""  # 原文摘要/內容，丟給分類器處理


@app.get("/api/categories")
def get_categories():
    """回傳系統定義的 5 大分類清單，前端篩選器用"""
    return {"categories": CATEGORIES}


@app.get("/api/articles")
def get_articles(
    date: Optional[str] = Query(None, description="YYYY-MM-DD，不填則回傳全部日期"),
    categories: Optional[str] = Query(None, description="逗號分隔，例如 Trends & Aesthetics,Sustainability & ESG"),
):
    cat_list = categories.split(",") if categories else None
    return {"articles": query_articles(date_filter=date, category_filter=cat_list)}


@app.get("/api/stats")
def get_stats_api(date: Optional[str] = Query(None)):
    return get_stats(date_filter=date)


@app.post("/api/articles")
def create_article(item: ArticleIn):
    """
    新增一篇文章：自動呼叫分類器產生 categories + summary，再寫入資料庫。
    這個端點同時被 RSS 爬蟲腳本與手動輸入使用。
    """
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


# ----- 前端靜態檔案 -----
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
