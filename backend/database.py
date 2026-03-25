import os
import sqlite3
from pathlib import Path

# Railway では DATA_DIR 環境変数でボリュームのマウントパスを指定
_data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DB_PATH = _data_dir / "data.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            title_ja TEXT,
            link TEXT NOT NULL UNIQUE,
            thumbnail TEXT,
            source TEXT NOT NULL,
            lang TEXT DEFAULT 'en',
            published_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # 既存DBへのマイグレーション
    try:
        conn.execute("ALTER TABLE posts ADD COLUMN title_ja TEXT")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE posts ADD COLUMN lang TEXT DEFAULT 'en'")
    except Exception:
        pass
    conn.commit()
    conn.close()
