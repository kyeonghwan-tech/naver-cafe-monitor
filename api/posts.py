"""
GET  /api/posts          - 게시글 목록 (네이버 카페 실시간 스크래핑)
GET  /api/posts?menu_id= - 특정 게시판만
"""
import os
import re
import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────────────────
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


def fetch_board(menu_id: str, per_page: int = 20) -> list[dict]:
    session = _make_session()

    # 1차: 내부 JSON API
    try:
        resp = session.get(
            "https://apis.naver.com/cafe-web/cafe2/ArticleListV2.json",
            params={
                "search.clubid": CAFE_ID,
                "search.menuid": menu_id,
                "search.page": 1,
                "search.perPage": per_page,
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
            if items:
                board_name = next((b["name"] for b in BOARDS if b["id"] == menu_id), menu_id)
                articles = []
                for item in items:
                    aid = str(item.get("articleId", ""))
                    title = item.get("subject", "")
                    matched = [kw for kw in IT_KEYWORDS if kw.lower() in title.lower()]
                    articles.append({
                        "article_id": aid,
                        "title": title,
                        "author": item.get("writerNickname", ""),
                        "written_at": str(item.get("writeDateTimestamp", "")),
                        "menu_id": menu_id,
                        "board_name": board_name,
                        "keywords": matched,
                        "status": "pending",
                        "url": f"https://cafe.naver.com/ArticleRead.nhn?clubid={CAFE_ID}&articleid={aid}",
                        "content": "",
                    })
                return articles
    except Exception as e:
        logger.warning("JSON API failed (menu %s): %s", menu_id, e)

    # 2차: HTML 파싱 fallback
    try:
        resp = session.get(
            "https://cafe.naver.com/ArticleList.nhn",
            params={
                "search.clubid": CAFE_ID,
                "search.menuid": menu_id,
                "search.page": 1,
                "search.perPage": per_page,
                "search.boardtype": "L",
            },
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        board_name = next((b["name"] for b in BOARDS if b["id"] == menu_id), menu_id)
        articles = []
        for tr in soup.select(".article-board tbody tr"):
            a_tag = tr.select_one(".td_article .article")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            m = re.search(r"articleid=(\d+)", href)
            if not m:
                continue
            aid = m.group(1)
            title = a_tag.get_text(strip=True)
            matched = [kw for kw in IT_KEYWORDS if kw.lower() in title.lower()]
            author_td = tr.select_one(".td_name")
            date_td   = tr.select_one(".td_date")
            articles.append({
                "article_id": aid,
                "title": title,
                "author": author_td.get_text(strip=True) if author_td else "",
                "written_at": date_td.get_text(strip=True) if date_td else "",
                "menu_id": menu_id,
                "board_name": board_name,
                "keywords": matched,
                "status": "pending",
                "url": f"https://cafe.naver.com/ArticleRead.nhn?clubid={CAFE_ID}&articleid={aid}",
                "content": "",
            })
        return articles
    except Exception as e:
        logger.error("HTML fallback failed (menu %s): %s", menu_id, e)
        return []


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        menu_id = qs.get("menu_id", [None])[0]
        status_filter = qs.get("status", [None])[0]

        try:
            if menu_id:
                boards_to_scan = [b for b in BOARDS if b["id"] == menu_id]
            else:
                boards_to_scan = BOARDS

            all_posts = []
            for board in boards_to_scan:
                posts = fetch_board(board["id"])
                all_posts.extend(posts)

            # status 아터
            if status_filter:
                all_posts = [p for p in all_posts if p.get("status") == status_filter]

            body = json.dumps(all_posts, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            logger.exception("posts handler error")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def log_message(self, format, *args):
        pass
