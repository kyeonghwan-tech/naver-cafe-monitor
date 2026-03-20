import os
from dotenv import load_dotenv

load_dotenv()

# ── Naver 인증 쿠키 ──────────────────────────────────────────────
NAVER_COOKIES = {
    "NID_AUT": os.getenv("NAVER_NID_AUT", ""),
    "NID_SES": os.getenv("NAVER_NID_SES", ""),
}

# ── GitHub 설정 ───────────────────────────────────────────────────
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
GITHUB_REPO     = os.getenv("GITHUB_REPO", "naver-cafe-it-posts")

# ── 카페 설정 ─────────────────────────────────────────────────────
CAFE_ID = "10733571"

BOARDS = [
    {"id": "530", "name": "교육훈련"},
    {"id": "14",  "name": "교육기획"},
    {"id": "334", "name": "강사추천"},
    {"id": "3",   "name": "자유게시판"},
]

# ── IT 교육 키워드 (대소문자 무관 매칭) ──────────────────────────
IT_KEYWORDS = [
    "AI", "인공지능", "바이브코딩", "vibe coding", "vibecoding",
    "AI 에이전트", "AI에이전트", "에이전트", "에이전틱",
    "머신러닝", "machine learning",
    "딥러닝", "deep learning",
    "ChatGPT", "챗GPT", "GPT", "LLM",
    "생성형 AI", "생성AI", "생성형AI",
    "프롬프트", "prompt engineering",
    "데이터사이언스", "데이터 사이언스", "data science",
    "빅데이터", "big data",
    "클라우드", "cloud",
    "파이썬", "python",
    "자동화", "RPA",
    "디지털 전환", "디지털전환", "DX",
    "코딩교육", "코딩 교육",
    "IT교육", "IT 교육",
    "정보화교육", "디지털리터러시", "디지털 리터러시",
]

# ── 폴링 주기 (분) ───────────────────────────────────────────────
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))

# ── 데이터 저장 경로 ──────────────────────────────────────────────
DATA_DIR      = os.path.join(os.path.dirname(__file__), "data")
SEEN_POSTS_DB = os.path.join(DATA_DIR, "seen_posts.db")
