"""
GET /api/system - 시스템 상태
"""
import json
from http.server import BaseHTTPRequestHandler
from datetime import datetime


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({
            "running": True,
            "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "next_scan": None,
            "remaining_secs": 600,
            "interval_minutes": 10,
            "mode": "serverless",
        }, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass
