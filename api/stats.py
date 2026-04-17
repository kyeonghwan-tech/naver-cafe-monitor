"""
GET /api/stats - 대시보드 통계 (네이버 카페 실시간 기반)
"""
import os
import re
import json
import logging
from http.server import BaseHTTPRequestHandler
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAFE_ID = "10733571"
BOARDS = [
    {"id": "530", "name": "교육훈련"},
    {"id": "14",  "name": "교육기획"},
    {"id": "334", "name": "강사추천"},
    {"id": "3",   "name": "자유게시판"},
]
IT_KEYWORDS = [
    "AI", "인공지능", "바이브코딩", "vibe coding", "vibecoding",
    "AI 에이전트", "AI에이전트", "에이전트", "에이전틱",
    "머신러닝", "machine learning", "딥러닝", "deep learning",
    "ChatGPT", "챗GPT", "GPT", "LLM",
    "생성형 AI", "생성AI", "생성형AI",
    "프롬프트", "prompt engineering",
    "데이터사이언스", "데이터 사이언스", "data science",
    "빅데이터", "big data", "클라우드", "cloud",
    "파이썬", "python", "자동화", "RPA",
    "디지털 전환", "디지털전환", "DX",
    "코딩교육", "코딩 교육", "IT교육", "IT 교육",
    "정보화교육", "디지털리터러시", "디지털 리터러시",
]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://cafe.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}


def _make_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    nid_aut = os.environ.get("NAVER_NID_AUT", "")
    nid_ses = os.environ.get("NAVER_NID_SES", "")
    if nid_aut and nid_ses:
        session.cookies.set("NID_AUT", nid_aut, domain=".naver.com")
        session.cookies.set("NID_SES", nid_ses, domain=".naver.com")
    return session


def count_board(board_id: str) -> int:
    """게시판의 IT 키워드 게시글 수 반환"""
    session = _make_session()
    try:
        resp = session.get(
            "https://apis.naver.com/cafe-web/cafe2/ArticleListV2.json",
            params={
                "search.clubid": CAFE_ID,
                "search.menuid": board_id,
                "search.page": 1,
                "search.perPage": 20,
                "search.boardtype": "L",
                "userType": "",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            items = (
                resp.json()
                .get("message", {})
                .get("result", {})
                .get("articleList", [])
            )
            return sum(
                1 for item in items
                if any(kw.lower() in item.get("subject", "").lower() for kw in IT_KEYWORDS)
            )
    except Exception as e:
        logger.warning("stats count failed (board %s): %s", board_id, e)
    return 0


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            by_board = {}
            total = 0
            for board in BOARDS:
                cnt = count_board(board["id"])
                by_board[board["name"]] = cnt
                total += cnt

            stats = {
                "total_today": total,
                "pending_today": total,
                "total_month": total,
                "response_rate": 0,
                "by_board": by_board,
                "by_status": {"pending": total},
                "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            body = json.dumps(stats, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.exception("stats handler error")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def log_message(self, format, *args):
        pass
