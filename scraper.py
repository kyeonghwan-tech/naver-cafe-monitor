"""
Naver Cafe 스크래퍼
- 게시판 목록 조회: Naver Cafe 내부 API (ArticleListV2.json)
- 게시글 본문 조회: ArticleRead 엔드포인트 (BeautifulSoup 파싱)
- 인증: NID_AUT / NID_SES 쿠키
"""

import re
import logging

import requests
from bs4 import BeautifulSoup

from config import CAFE_ID, BOARDS, IT_KEYWORDS, NAVER_COOKIES
import db

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://cafe.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

# ── DB 위임 (db.py로 통합) ───────────────────────────────────────

def init_db():
    db.init_db()

def is_seen(article_id: str) -> bool:
    return db.is_seen(article_id)

def mark_seen(article_id: str, menu_id: str, title: str):
    db.mark_seen(article_id, menu_id, title)


# ── 세션 생성 ─────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.cookies.update(NAVER_COOKIES)
    return session


# ── 게시판 목록 조회 ──────────────────────────────────────────────

def fetch_article_list(menu_id: str, page: int = 1, per_page: int = 20) -> list[dict]:
    """
    Naver Cafe 내부 API로 게시글 목록을 가져옵니다.
    JSON 응답 실패 시 HTML 파싱으로 fallback.
    """
    session = _make_session()

    # ── 1차 시도: 내부 JSON API ──────────────────────────────────
    json_url = "https://apis.naver.com/cafe-web/cafe2/ArticleListV2.json"
    params = {
        "search.clubid":  CAFE_ID,
        "search.menuid":  menu_id,
        "search.page":    page,
        "search.perPage": per_page,
        "search.boardtype": "L",
        "userType": "",
    }
    try:
        resp = session.get(json_url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            items = (
                data.get("message", {})
                    .get("result", {})
                    .get("articleList", [])
            )
            articles = []
            for item in items:
                articles.append({
                    "id":      str(item.get("articleId", "")),
                    "title":   item.get("subject", ""),
                    "author":  item.get("writerNickname", ""),
                    "date":    item.get("writeDateTimestamp", ""),
                    "menu_id": menu_id,
                })
            if articles:
                logger.debug("JSON API: %d articles from menu %s", len(articles), menu_id)
                return articles
    except Exception as e:
        logger.warning("JSON API failed (menu %s): %s", menu_id, e)

    # ── 2차 시도: HTML 파싱 ──────────────────────────────────────
    html_url = "https://cafe.naver.com/ArticleList.nhn"
    params_html = {
        "search.clubid":    CAFE_ID,
        "search.menuid":    menu_id,
        "search.page":      page,
        "search.perPage":   per_page,
        "search.boardtype": "L",
    }
    try:
        resp = session.get(html_url, params=params_html, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        for tr in soup.select(".article-board tbody tr"):
            a_tag = tr.select_one(".td_article .article")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            m = re.search(r"articleid=(\d+)", href)
            if not m:
                continue
            article_id = m.group(1)
            title = a_tag.get_text(strip=True)
            author_td = tr.select_one(".td_name")
            date_td   = tr.select_one(".td_date")
            articles.append({
                "id":      article_id,
                "title":   title,
                "author":  author_td.get_text(strip=True) if author_td else "",
                "date":    date_td.get_text(strip=True) if date_td else "",
                "menu_id": menu_id,
            })
        logger.debug("HTML fallback: %d articles from menu %s", len(articles), menu_id)
        return articles
    except Exception as e:
        logger.error("HTML fallback failed (menu %s): %s", menu_id, e)
        return []


# ── 게시글 본문 조회 ──────────────────────────────────────────────

def fetch_article_content(article_id: str) -> str:
    """게시글 본문 텍스트를 반환합니다."""
    session = _make_session()

    # iframe 내부 URL로 본문 접근
    url = "https://cafe.naver.com/ArticleRead.nhn"
    params = {
        "clubid":    CAFE_ID,
        "articleid": article_id,
        "boardtype": "L",
    }
    try:
        resp = session.get(url, params=params, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # 본문 영역 선택 (다양한 클래스명 대응)
        content_area = (
            soup.select_one(".se-main-container")
            or soup.select_one(".article_body")
            or soup.select_one("#tbody")
            or soup.select_one(".ContentRenderer")
        )
        if content_area:
            return content_area.get_text(separator="\n", strip=True)

        # fallback: body 전체
        body = soup.find("body")
        return body.get_text(separator="\n", strip=True) if body else ""
    except Exception as e:
        logger.error("fetch_article_content failed (%s): %s", article_id, e)
        return ""


# ── 키워드 매칭 ───────────────────────────────────────────────────

def contains_it_keyword(text: str) -> list[str]:
    """텍스트에 포함된 IT 키워드 목록을 반환합니다."""
    text_lower = text.lower()
    matched = [kw for kw in IT_KEYWORDS if kw.lower() in text_lower]
    return matched


# ── 전체 모니터링 실행 ────────────────────────────────────────────

def scan_all_boards() -> list[dict]:
    """
    모든 게시판을 스캔하여 IT 키워드가 포함된 신규 게시글 목록을 반환합니다.
    각 항목: {id, title, author, date, menu_id, board_name, keywords, content, url}
    """
    init_db()
    results = []

    for board in BOARDS:
        menu_id    = board["id"]
        board_name = board["name"]
        logger.info("[%s] 게시판 스캔 시작...", board_name)

        articles = fetch_article_list(menu_id, page=1, per_page=30)

        for article in articles:
            article_id = article["id"]
            title      = article["title"]

            if is_seen(article_id):
                continue

            # 제목에서 1차 키워드 체크 (빠른 필터)
            matched_in_title = contains_it_keyword(title)

            # 본문까지 확인
            content = fetch_article_content(article_id)
            matched_in_content = contains_it_keyword(content)

            all_matched = list(dict.fromkeys(matched_in_title + matched_in_content))

            if all_matched:
                article_url = (
                    f"https://cafe.naver.com/ArticleRead.nhn"
                    f"?clubid={CAFE_ID}&articleid={article_id}"
                )
                logger.info(
                    "[%s] 매칭 게시글: %s | 키워드: %s",
                    board_name, title, ", ".join(all_matched),
                )
                results.append({
                    **article,
                    "board_name": board_name,
                    "keywords":   all_matched,
                    "content":    content,
                    "url":        article_url,
                })

            # 신규 게시글은 확인 여부와 무관하게 seen 처리
            mark_seen(article_id, menu_id, title)

            # IT 키워드 매칭 게시글은 DB에 저장
            if all_matched:
                db.save_post({
                    **article,
                    "board_name": board_name,
                    "keywords":   all_matched,
                    "content":    content,
                    "url":        article_url,
                })

    return results
