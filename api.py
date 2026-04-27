"""
Flask REST API
GET  /api/stats              - 대시보드 통계
GET  /api/posts              - 게시글 목록 (?menu_id=&status=&limit=&offset=)
GET  /api/posts/<article_id> - 게시글 상세
PATCH/api/posts/<article_id> - 응대 상태 변경 {status: pending|comment|proposal|done}
GET  /api/system             - 시스템 상태 (다음 스캔 시간 등)
"""

import threading
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
import os

import db
from config import POLL_INTERVAL_MINUTES, BOARDS

app = Flask(__name__, static_folder="web", static_url_path="")

# 다음 스캔 시간 공유 (main.py에서 업데이트)
_next_scan: datetime | None = None
_last_scan: datetime | None = None
_lock = threading.Lock()


def set_scan_times(last: datetime, next_: datetime):
    global _last_scan, _next_scan
    with _lock:
        _last_scan = last
        _next_scan = next_


# ── 정적 파일 ─────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("web", "index.html")


# ── API ──────────────────────────────────────────────────────────

@app.route("/api/stats")
def stats():
    return jsonify(db.get_stats())


@app.route("/api/posts")
def posts():
    menu_id = request.args.get("menu_id")
    status  = request.args.get("status")
    limit   = int(request.args.get("limit", 100))
    offset  = int(request.args.get("offset", 0))
    data    = db.get_posts(menu_id=menu_id, status=status, limit=limit, offset=offset)
    return jsonify(data)


@app.route("/api/posts/<article_id>")
def post_detail(article_id):
    post = db.get_post(article_id)
    if not post:
        return jsonify({"error": "Not found"}), 404
    return jsonify(post)


@app.route("/api/posts/<article_id>", methods=["PATCH"])
def update_post(article_id):
    body   = request.get_json(force=True)
    status = body.get("status")
    valid  = {"pending", "comment", "proposal", "done"}
    if status not in valid:
        return jsonify({"error": f"status must be one of {valid}"}), 400
    db.update_status(article_id, status)
    return jsonify({"ok": True, "article_id": article_id, "status": status})


@app.route("/api/system")
def system():
    with _lock:
        last = _last_scan.strftime("%Y-%m-%d %H:%M:%S") if _last_scan else None
        nxt  = _next_scan.strftime("%Y-%m-%d %H:%M:%S") if _next_scan else None
        remaining = None
        if _next_scan:
            secs = int((_next_scan - datetime.now()).total_seconds())
            remaining = max(0, secs)
    return jsonify({
        "running":          True,
        "last_scan":        last,
        "next_scan":        nxt,
        "remaining_secs":   remaining,
        "interval_minutes": POLL_INTERVAL_MINUTES,
        "boards":           BOARDS,
    })


@app.route("/api/boards")
def boards():
    return jsonify(BOARDS)


@app.route("/api/setup-playwright")
def setup_playwright():
    import subprocess, sys, os
    base = os.path.dirname(os.path.abspath(__file__))
    results = {}
    r1 = subprocess.run(["git", "-C", base, "pull"], capture_output=True, text=True)
    results["git_pull"] = r1.stdout + r1.stderr
    r2 = subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], capture_output=True, text=True)
    results["pip_install"] = (r2.stdout + r2.stderr)[-800:]
    r3 = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True)
    results["playwright_install"] = (r3.stdout + r3.stderr)[-800:]
    results["ok"] = r2.returncode == 0 and r3.returncode == 0
    return jsonify(results)


@app.route("/api/fix-content")
def fix_content():
    import subprocess, sys, os
    base = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(base, "fix_content.py")
    r = subprocess.run([sys.executable, script], capture_output=True, text=True, cwd=base)
    return jsonify({"output": r.stdout[-2000:], "error": r.stderr[-500:], "ok": r.returncode == 0})


def run(host="0.0.0.0", port=5000, debug=False):
    db.init_db()
    app.run(host=host, port=port, debug=debug, use_reloader=False)
