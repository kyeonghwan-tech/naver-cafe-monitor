"""
네이버 카페 IT 교육 게시글 모니터 — 진입점

사용법:
    python main.py            # 스케줄러 시작 (30분 간격)
    python main.py --once     # 즉시 1회 실행 후 종료
    python main.py --interval 10  # 10분 간격으로 실행
"""

import argparse
import logging
import sys
import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from config import POLL_INTERVAL_MINUTES, GITHUB_TOKEN, GITHUB_USERNAME, NAVER_COOKIES
from scraper import scan_all_boards
from uploader import upload_articles

# ── 로깅 설정 ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False)),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ── 환경 검증 ─────────────────────────────────────────────────────

def validate_config() -> bool:
    ok = True
    if not NAVER_COOKIES.get("NID_AUT") or not NAVER_COOKIES.get("NID_SES"):
        logger.error(
            "Naver 인증 쿠키가 설정되지 않았습니다.\n"
            ".env 파일에 NAVER_NID_AUT, NAVER_NID_SES 를 입력해 주세요."
        )
        ok = False
    if not GITHUB_TOKEN:
        logger.error(".env 파일에 GITHUB_TOKEN 을 입력해 주세요.")
        ok = False
    if not GITHUB_USERNAME:
        logger.error(".env 파일에 GITHUB_USERNAME 을 입력해 주세요.")
        ok = False
    return ok


# ── 단일 스캔 실행 ────────────────────────────────────────────────

def run_scan():
    logger.info("=" * 60)
    logger.info("스캔 시작: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    articles = scan_all_boards()

    if not articles:
        logger.info("IT 교육 관련 신규 게시글 없음.")
        return

    logger.info("발견된 게시글: %d건 → GitHub 업로드 시작", len(articles))
    result = upload_articles(articles)
    logger.info(
        "GitHub 업로드 완료 — 성공: %d / 실패: %d",
        result["success"], result["fail"],
    )


# ── 진입점 ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="네이버 카페 IT 교육 게시글 모니터")
    parser.add_argument(
        "--once", action="store_true",
        help="즉시 1회 실행 후 종료"
    )
    parser.add_argument(
        "--interval", type=int, default=POLL_INTERVAL_MINUTES,
        help=f"폴링 주기 (분, 기본: {POLL_INTERVAL_MINUTES})"
    )
    args = parser.parse_args()

    if not validate_config():
        sys.exit(1)

    if args.once:
        run_scan()
        return

    # 스케줄러 모드
    interval = args.interval
    logger.info(
        "스케줄러 시작 — %d분 간격으로 실행됩니다. 종료하려면 Ctrl+C 를 누르세요.",
        interval,
    )

    # 시작하자마자 1회 즉시 실행
    run_scan()

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(run_scan, "interval", minutes=interval, id="cafe_monitor")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("모니터 종료.")


if __name__ == "__main__":
    main()
