from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from pathlib import Path
from database import init_db, get_connection
from scraper import fetch_all, get_translator

app = FastAPI()

FRONTEND_DIR = Path(__file__).parent / "frontend"

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


@app.post("/api/reset")
def reset():
    conn = get_connection()
    conn.execute("DELETE FROM posts")
    conn.commit()
    conn.close()
    saved = fetch_all()
    return {"saved": saved}


@app.get("/api/debug-sample")
def debug_sample():
    """DBの最初の3件のtitleとtitle_jaを確認する"""
    conn = get_connection()
    rows = conn.execute("SELECT id, title, title_ja, source FROM posts LIMIT 3").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/cleanup-bad-data")
def cleanup_bad_data():
    """コンフリクトマーカーが混入したデータを削除して再収集"""
    conn = get_connection()
    result = conn.execute("DELETE FROM posts WHERE title LIKE '%<<<<<<<<%'")
    deleted = result.rowcount
    conn.commit()
    conn.close()
    saved = fetch_all()
    return {"deleted": deleted, "saved": saved}


@app.post("/api/translate-all")
def translate_all():
    translator = get_translator()
    if not translator:
        return {"error": "DEEPL_API_KEY not set"}
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title FROM posts WHERE title_ja IS NULL AND lang = 'en'"
    ).fetchall()
    updated = 0
    for row in rows:
        try:
            result = translator.translate_text(row["title"], target_lang="JA")
            conn.execute(
                "UPDATE posts SET title_ja = ? WHERE id = ?",
                (result.text, row["id"]),
            )
            updated += 1
        except Exception as e:
            print(f"[translate] Error: {e}")
            break
    conn.commit()
    conn.close()
    return {"translated": updated}


# フロントエンドの静的ファイルを配信
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
