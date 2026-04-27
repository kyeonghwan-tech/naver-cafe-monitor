"""
Flask REST API + 정적 웹 대시보드 서빙
"""

import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory

import db
from config import POLL_INTERVAL_MINUTES, BOARDS

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_WEB_DIR  = os.path.join(_BASE_DIR, "web")

app = Flask(__name__, static_folder=_WEB_DIR, static_url_path="")

_db_initialized = False

@app.before_request
def ensure_db():
    global _db_initialized
    if not _db_initialized:
        db.init_db()
        _db_initialized = True


# ── 정적 파일 ─────────────────────────────────────────────────────

@app.route("/")
def index():
    html_path = os.path.join(_WEB_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    from flask import Response
    return Response(content, mimetype="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })


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
    times = db.get_scan_times()
    last  = times.get("last_scan")
    nxt   = times.get("next_scan")
    remaining = None
    if nxt:
        try:
            secs = int((datetime.fromisoformat(nxt) - datetime.now()).total_seconds())
            remaining = max(0, secs)
        except Exception:
            pass
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


@app.route("/api/cron")
def cron():
    cron_secret = os.environ.get("CRON_SECRET", "")
    if cron_secret:
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {cron_secret}":
            return jsonify({"error": "Unauthorized"}), 401

    from scraper import scan_all_boards
    from uploader import upload_articles

    articles = scan_all_boards()
    upload_result = {"success": 0, "fail": 0}
    if articles:
        upload_result = upload_articles(articles)

    now = datetime.now()
    db.set_scan_times(last=now, next_=now + timedelta(minutes=POLL_INTERVAL_MINUTES))

    return jsonify({
        "ok":      True,
        "scanned": len(articles),
        "upload":  upload_result,
    })


def run(host="0.0.0.0", port=5000, debug=False):
    db.init_db()
    app.run(host=host, port=port, debug=debug, use_reloader=False)
