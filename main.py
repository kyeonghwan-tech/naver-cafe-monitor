"""
네이버 카페 IT 교육 게시글 모니터 — 진입점

사용법:
    python main.py            # 스케줄러 + 웹 대시보드 동시 실행
    python main.py --once     # 즉시 1회 스캔 후 종료
    python main.py --no-web   # 웹 서버 없이 스캔만 실행
    python main.py --port 8080  # 웹 서버 포트 변경 (기본 5000)
"""

import argparse
import logging
import sys
import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

import db
from config import POLL_INTERVAL_MINUTES
from scraper import scan_all_boards
from uploader import upload_articles

# ── 로깅 설정 ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ── 환경 검증 ─────────────────────────────────────────────────────
def validate_config() -> bool:
    from config import NAVER_COOKIES, GITHUB_TOKEN, GITHUB_USERNAME
    ok = True
    if not NAVER_COOKIES.get("NID_AUT") or not NAVER_COOKIES.get("NID_SES"):
        logger.error(".env 파일에 NAVER_NID_AUT, NAVER_NID_SES 를 입력해 주세요.")
        ok = False
    if not GITHUB_TOKEN:
        logger.error(".env 파일에 GITHUB_TOKEN 을 입력해 주세요.")
        ok = False
    if not GITHUB_USERNAME:
        logger.error(".env 파일에 GITHUB_USERNAME 을 입력해 주세요.")
        ok = False
    return ok


# ── 단일 스캔 ────────────────────────────────────────────────────
def run_scan():
    logger.info("=" * 55)
    logger.info("스캔 시작: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 55)

    articles = scan_all_boards()

    if not articles:
        logger.info("IT 교육 관련 신규 게시글 없음.")
    else:
        logger.info("발견: %d건 → GitHub 업로드 시작", len(articles))
        result = upload_articles(articles)
        logger.info("GitHub 완료 — 성공: %d / 실패: %d", result["success"], result["fail"])

    # 다음 스캔 시간 업데이트 (API 서버에 공유)
    try:
        import api
        api.set_scan_times(
            last=datetime.now(),
            next_=datetime.now() + timedelta(minutes=POLL_INTERVAL_MINUTES),
        )
    except Exception:
        pass


# ── 진입점 ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="네이버 카페 IT 교육 게시글 모니터")
    parser.add_argument("--once",    action="store_true", help="1회 실행 후 종료")
    parser.add_argument("--no-web",  action="store_true", help="웹 서버 없이 실행")
    parser.add_argument("--port",    type=int, default=5000, help="웹 서버 포트 (기본 5000)")
    parser.add_argument("--interval",type=int, default=POLL_INTERVAL_MINUTES, help="폴링 주기(분)")
    args = parser.parse_args()

    if not validate_config():
        sys.exit(1)

    db.init_db()

    # ── 1회 실행 모드 ─────────────────────────────────────────
    if args.once:
        run_scan()
        return

    # ── 웹 서버 백그라운드 실행 ───────────────────────────────
    if not args.no_web:
        import api
        web_thread = threading.Thread(
            target=api.run,
            kwargs={"host": "0.0.0.0", "port": args.port, "debug": False},
            daemon=True,
        )
        web_thread.start()
        logger.info("웹 대시보드 시작: http://localhost:%d", args.port)

    # ── 스케줄러 시작 ─────────────────────────────────────────
    interval = args.interval
    logger.info("스케줄러 시작 — %d분 간격. 종료: Ctrl+C", interval)

    run_scan()  # 즉시 1회 실행

    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(run_scan, "interval", minutes=interval, id="cafe_monitor")
    scheduler.start()

    try:
        # 메인 스레드 유지
        import time
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("모니터 종료.")


if __name__ == "__main__":
    main()
