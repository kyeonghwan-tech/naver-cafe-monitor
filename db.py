"""
SQLite 데이터베이스 레이어
- posts 테이블: 탐지된 게시글 전체 저장 + 응대 상태 관리
- seen_posts 테이블: 중복 탐지 방지 (기존 유지)
"""

import sqlite3
import json
import os
from datetime import datetime
from config import DATA_DIR, SEEN_POSTS_DB, CAFE_ID

DB_PATH = SEEN_POSTS_DB  # 기존 DB 재사용


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_posts (
            cafe_id    TEXT NOT NULL,
            article_id TEXT NOT NULL,
            menu_id    TEXT NOT NULL,
            title      TEXT,
            seen_at    TEXT,
            PRIMARY KEY (cafe_id, article_id)
        );

        CREATE TABLE IF NOT EXISTS posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cafe_id     TEXT NOT NULL,
            article_id  TEXT NOT NULL,
            menu_id     TEXT NOT NULL,
            board_name  TEXT NOT NULL,
            title       TEXT NOT NULL,
            author      TEXT,
            written_at  TEXT,
            content     TEXT,
            url         TEXT,
            keywords    TEXT,
            status      TEXT DEFAULT 'pending',
            detected_at TEXT NOT NULL,
            responded_at TEXT,
            UNIQUE(cafe_id, article_id)
        );

        CREATE INDEX IF NOT EXISTS idx_posts_detected ON posts(detected_at DESC);
        CREATE INDEX IF NOT EXISTS idx_posts_status   ON posts(status);
        CREATE INDEX IF NOT EXISTS idx_posts_menu     ON posts(menu_id);
    """)
    conn.commit()
    conn.close()


# ── 중복 확인 / seen 처리 ─────────────────────────────────────────

def is_seen(article_id: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM seen_posts WHERE cafe_id=? AND article_id=?",
        (CAFE_ID, article_id),
    ).fetchone()
    conn.close()
    return row is not None


def mark_seen(article_id: str, menu_id: str, title: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO seen_posts VALUES (?,?,?,?,?)",
        (CAFE_ID, article_id, menu_id, title, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


# ── 게시글 저장 ───────────────────────────────────────────────────

def save_post(article: dict):
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO posts
           (cafe_id, article_id, menu_id, board_name, title, author,
            written_at, content, url, keywords, status, detected_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            CAFE_ID,
            article["id"],
            article["menu_id"],
            article["board_name"],
            article["title"],
            article.get("author", ""),
            str(article.get("date", "")),
            article.get("content", ""),
            article.get("url", ""),
            json.dumps(article.get("keywords", []), ensure_ascii=False),
            "pending",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


# ── 응대 상태 업데이트 ────────────────────────────────────────────

def update_status(article_id: str, status: str):
    """status: pending | comment | proposal | done"""
    conn = get_conn()
    conn.execute(
        """UPDATE posts SET status=?, responded_at=?
           WHERE cafe_id=? AND article_id=?""",
        (status, datetime.now().isoformat(), CAFE_ID, article_id),
    )
    conn.commit()
    conn.close()


# ── 조회 ─────────────────────────────────────────────────────────

def get_posts(menu_id=None, status=None, limit=100, offset=0) -> list[dict]:
    conn = get_conn()
    where, params = ["cafe_id=?"], [CAFE_ID]
    if menu_id:
        where.append("menu_id=?")
        params.append(menu_id)
    if status:
        where.append("status=?")
        params.append(status)
    params += [limit, offset]
    rows = conn.execute(
        f"""SELECT * FROM posts WHERE {' AND '.join(where)}
            ORDER BY detected_at DESC LIMIT ? OFFSET ?""",
        params,
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["keywords"] = json.loads(d["keywords"] or "[]")
        result.append(d)
    return result


def get_post(article_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM posts WHERE cafe_id=? AND article_id=?",
        (CAFE_ID, article_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["keywords"] = json.loads(d["keywords"] or "[]")
    return d


def get_stats() -> dict:
    conn = get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    total_today = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE cafe_id=? AND detected_at LIKE ?",
        (CAFE_ID, f"{today}%"),
    ).fetchone()[0]

    pending_today = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE cafe_id=? AND status='pending' AND detected_at LIKE ?",
        (CAFE_ID, f"{today}%"),
    ).fetchone()[0]

    total_month = conn.execute(
        "SELECT COUNT(*) FROM posts WHERE cafe_id=? AND detected_at LIKE ?",
        (CAFE_ID, f"{datetime.now().strftime('%Y-%m')}%"),
    ).fetchone()[0]

    by_board = conn.execute(
        """SELECT board_name, COUNT(*) as cnt FROM posts
           WHERE cafe_id=? AND detected_at LIKE ?
           GROUP BY board_name""",
        (CAFE_ID, f"{today}%"),
    ).fetchall()

    by_status = conn.execute(
        """SELECT status, COUNT(*) as cnt FROM posts
           WHERE cafe_id=? AND detected_at LIKE ?
           GROUP BY status""",
        (CAFE_ID, f"{today}%"),
    ).fetchall()

    conn.close()

    status_map = {r["status"]: r["cnt"] for r in by_status}
    responded = total_today - pending_today
    rate = round(responded / total_today * 100) if total_today else 0

    return {
        "total_today":   total_today,
        "pending_today": pending_today,
        "total_month":   total_month,
        "response_rate": rate,
        "by_board":      {r["board_name"]: r["cnt"] for r in by_board},
        "by_status":     status_map,
    }
