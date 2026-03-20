"""
GitHub 업로더
- 지정된 레포지토리가 없으면 자동 생성
- 발견된 게시글을 Markdown 파일로 커밋
- 파일 경로: posts/{board_name}/{YYYY-MM}/{article_id}_{slug}.md
"""

import base64
import logging
import re
from datetime import datetime

import requests

from config import GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_REPO

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ── 레포지토리 관리 ───────────────────────────────────────────────

def ensure_repo_exists() -> bool:
    """레포지토리가 없으면 생성합니다. 성공 여부를 반환합니다."""
    url = f"{API_BASE}/repos/{GITHUB_USERNAME}/{GITHUB_REPO}"
    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code == 200:
        logger.debug("레포지토리 이미 존재: %s/%s", GITHUB_USERNAME, GITHUB_REPO)
        return True

    if resp.status_code == 404:
        # 레포지토리 생성
        create_url = f"{API_BASE}/user/repos"
        payload = {
            "name":        GITHUB_REPO,
            "description": "네이버 카페 IT 교육 게시글 자동 수집",
            "private":     False,
            "auto_init":   True,  # README.md 자동 생성 (첫 커밋 필요)
        }
        resp2 = requests.post(create_url, json=payload, headers=HEADERS, timeout=15)
        if resp2.status_code in (200, 201):
            logger.info("레포지토리 생성 완료: %s/%s", GITHUB_USERNAME, GITHUB_REPO)
            return True
        logger.error("레포지토리 생성 실패: %s %s", resp2.status_code, resp2.text)
        return False

    logger.error("레포지토리 확인 실패: %s %s", resp.status_code, resp.text)
    return False


# ── 파일 경로 생성 ────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 40) -> str:
    """파일명에 사용 가능한 슬러그로 변환합니다."""
    text = re.sub(r"[^\w\s가-힣]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:max_len]


def _build_file_path(article: dict) -> str:
    """posts/{board_name}/{YYYY-MM}/{article_id}_{slug}.md"""
    now         = datetime.now().strftime("%Y-%m")
    board_slug  = _slugify(article["board_name"], 20)
    title_slug  = _slugify(article["title"])
    article_id  = article["id"]
    return f"posts/{board_slug}/{now}/{article_id}_{title_slug}.md"


# ── Markdown 본문 생성 ────────────────────────────────────────────

def _build_markdown(article: dict) -> str:
    keywords_str = ", ".join(article.get("keywords", []))
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content      = article.get("content", "").strip() or "_본문을 가져올 수 없습니다._"

    return f"""# {article['title']}

| 항목 | 내용 |
|------|------|
| 게시판 | {article['board_name']} |
| 작성자 | {article.get('author', '-')} |
| 작성일 | {article.get('date', '-')} |
| 원문 URL | [{article['url']}]({article['url']}) |
| 탐지 키워드 | `{keywords_str}` |
| 수집 일시 | {collected_at} |

---

## 본문

{content}
"""


# ── GitHub 파일 커밋 ──────────────────────────────────────────────

def _get_file_sha(file_path: str) -> str | None:
    """이미 존재하는 파일의 SHA를 가져옵니다 (업데이트 시 필요)."""
    url = f"{API_BASE}/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{file_path}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None


def upload_article(article: dict) -> bool:
    """
    게시글 하나를 GitHub에 Markdown 파일로 업로드합니다.
    반환값: 성공 여부
    """
    file_path = _build_file_path(article)
    markdown  = _build_markdown(article)
    encoded   = base64.b64encode(markdown.encode("utf-8")).decode("utf-8")

    sha        = _get_file_sha(file_path)
    commit_msg = f"[{article['board_name']}] {article['title']}"

    url     = f"{API_BASE}/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{file_path}"
    payload = {
        "message": commit_msg,
        "content": encoded,
    }
    if sha:
        payload["sha"] = sha  # 파일 업데이트

    resp = requests.put(url, json=payload, headers=HEADERS, timeout=20)
    if resp.status_code in (200, 201):
        html_url = resp.json().get("content", {}).get("html_url", "")
        logger.info("GitHub 업로드 성공: %s", html_url or file_path)
        return True

    logger.error("GitHub 업로드 실패 (%s): %s %s", file_path, resp.status_code, resp.text)
    return False


# ── 일괄 업로드 ───────────────────────────────────────────────────

def upload_articles(articles: list[dict]) -> dict:
    """
    여러 게시글을 업로드하고 결과를 요약합니다.
    반환값: {"success": int, "fail": int}
    """
    if not articles:
        return {"success": 0, "fail": 0}

    if not ensure_repo_exists():
        logger.error("레포지토리 준비 실패 — 업로드 중단")
        return {"success": 0, "fail": len(articles)}

    success = fail = 0
    for article in articles:
        if upload_article(article):
            success += 1
        else:
            fail += 1

    logger.info("업로드 완료 — 성공: %d, 실패: %d", success, fail)
    return {"success": success, "fail": fail}
