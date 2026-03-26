# database.py — SQLite操作
import sqlite3
import uuid
import json
from datetime import datetime
from config import DB_PATH


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            query TEXT,
            device TEXT,
            locations TEXT,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'running'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            location_name TEXT,
            rank INTEGER,
            title TEXT,
            url TEXT,
            snippet TEXT,
            is_ad BOOLEAN DEFAULT 0,
            ad_position TEXT,
            page INTEGER,
            category TEXT,
            has_meta_desc BOOLEAN,
            meta_desc_length INTEGER,
            has_structured_data BOOLEAN,
            has_ogp BOOLEAN,
            page_text_length INTEGER,
            site_status TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()


def create_session(query, device, locations):
    session_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    name = f"{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    locations_json = json.dumps([loc["name"] for loc in locations], ensure_ascii=False)

    conn = get_connection()
    conn.execute(
        "INSERT INTO sessions (id, name, query, device, locations, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, name, query, device, locations_json, now, "running")
    )
    conn.commit()
    conn.close()
    return session_id


def update_session_status(session_id, status):
    conn = get_connection()
    conn.execute("UPDATE sessions SET status = ? WHERE id = ?", (status, session_id))
    conn.commit()
    conn.close()


def insert_result(session_id, result_data):
    conn = get_connection()
    conn.execute("""
        INSERT INTO results (
            session_id, location_name, rank, title, url, snippet,
            is_ad, ad_position, page, category,
            has_meta_desc, meta_desc_length, has_structured_data,
            has_ogp, page_text_length, site_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        result_data.get("location_name"),
        result_data.get("rank"),
        result_data.get("title"),
        result_data.get("url"),
        result_data.get("snippet"),
        result_data.get("is_ad", False),
        result_data.get("ad_position"),
        result_data.get("page"),
        result_data.get("category"),
        result_data.get("has_meta_desc"),
        result_data.get("meta_desc_length"),
        result_data.get("has_structured_data"),
        result_data.get("has_ogp"),
        result_data.get("page_text_length"),
        result_data.get("site_status"),
    ))
    conn.commit()
    conn.close()


def get_session(session_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_all_sessions():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_results(session_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM results WHERE session_id = ? ORDER BY location_name, is_ad DESC, rank",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_results_count(session_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM results WHERE session_id = ?",
        (session_id,)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


if __name__ == "__main__":
    init_db()
    print("DB初期化完了")
