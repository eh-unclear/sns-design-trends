from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from pathlib import Path
from database import init_db, get_connection
from scraper import fetch_all

app = FastAPI()

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# スケジューラー設定（6時間ごとに自動収集）
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_all, "interval", hours=6, id="scrape_job")


@app.on_event("startup")
def startup():
    init_db()
    fetch_all()  # 起動時に一度収集
    scheduler.start()


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()


@app.get("/api/posts")
def get_posts(
    source: str = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    conn = get_connection()
    if source:
        rows = conn.execute(
            """
            SELECT * FROM posts
            WHERE source = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (source, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM posts
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/sources")
def get_sources():
    conn = get_connection()
    rows = conn.execute(
        "SELECT source, COUNT(*) as count FROM posts GROUP BY source ORDER BY count DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/refresh")
def manual_refresh():
    saved = fetch_all()
    return {"saved": saved}


# フロントエンドの静的ファイルを配信
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
