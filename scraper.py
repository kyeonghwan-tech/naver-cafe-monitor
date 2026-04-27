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
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

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
    session = _make_session()

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
                return articles
    except Exception as e:
        logger.warning("JSON API failed (menu %s): %s", menu_id, e)

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
        return articles
    except Exception as e:
        logger.error("HTML fallback failed (menu %s): %s", menu_id, e)
        return []


# ── 게시글 본문 조회 ──────────────────────────────────────────────

def fetch_article_content(article_id: str) -> str:
    """게시글 본문 텍스트를 반환합니다. (Playwright로 JS 렌더링 후 파싱)"""
    url = (
        f"https://cafe.naver.com/ArticleRead.nhn"
        f"?clubid={CAFE_ID}&articleid={article_id}&boardtype=L&inframe=1"
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            # 네이버 로그인 쿠키 세팅
            context.add_cookies([
                {"name": "NID_AUT", "value": NAVER_COOKIES.get("NID_AUT", ""),
                 "domain": ".naver.com", "path": "/"},
                {"name": "NID_SES", "value": NAVER_COOKIES.get("NID_SES", ""),
                 "domain": ".naver.com", "path": "/"},
            ])
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            # 본문 영역이 렌더링될 때까지 대기
            for selector in [".se-main-container", ".article_body", "#tbody", ".ContentRenderer"]:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    break
                except PlaywrightTimeoutError:
                    continue

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        content_area = (
            soup.select_one(".se-main-container")
            or soup.select_one(".article_body")
            or soup.select_one("#tbody")
            or soup.select_one(".ContentRenderer")
        )
        if content_area:
            text = content_area.get_text(separator="\n", strip=True)
            if "web-pc doesn't work properly" in text:
                return ""
            return text

        body = soup.find("body")
        if body:
            text = body.get_text(separator="\n", strip=True)
            if "web-pc doesn't work properly" in text:
                return ""
            return text
        return ""
    except Exception as e:
        logger.error("fetch_article_content (playwright) failed (%s): %s", article_id, e)
        return ""


# ── 키워드 매칭 ───────────────────────────────────────────────────

def contains_it_keyword(text: str) -> list[str]:
    text_lower = text.lower()
    matched = [kw for kw in IT_KEYWORDS if kw.lower() in text_lower]
    return matched


# ── 전체 모니터링 실행 ────────────────────────────────────────────

def scan_all_boards() -> list[dict]:
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

            matched_in_title = contains_it_keyword(title)
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

            mark_seen(article_id, menu_id, title)

            if all_matched:
                db.save_post({
                    **article,
                    "board_name": board_name,
                    "keywords":   all_matched,
                    "content":    content,
                    "url":        article_url,
                })

    return results
