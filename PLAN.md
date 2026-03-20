# 개발 계획서: 네이버 카페 IT 교육 게시글 모니터링 시스템

**버전:** 1.0
**작성일:** 2026-03-20
**레포지토리:** https://github.com/kyeonghwan-tech/naver-cafe-monitor

---

## 1. 현재 구현 현황

| 모듈 | 파일 | 상태 | 설명 |
|------|------|------|------|
| 스크래퍼 | `scraper.py` | ✅ 완료 | Naver Cafe JSON API + HTML fallback |
| DB 레이어 | `db.py` | ✅ 완료 | SQLite (seen_posts + posts 테이블) |
| GitHub 업로더 | `uploader.py` | ✅ 완료 | Markdown 파일 자동 커밋 |
| REST API | `api.py` | ✅ 완료 | Flask 5개 엔드포인트 |
| 웹 대시보드 | `web/index.html` | ✅ 완료 | Vanilla JS, 응대 상태 관리 |
| 진입점 | `main.py` | ✅ 완료 | BackgroundScheduler + Flask 통합 |
| 설정 | `config.py` | ✅ 완료 | 환경변수, 키워드, 게시판 정의 |
| 자동 시작 | `start.bat` | ✅ 완료 | Windows 시작프로그램 등록 |

---

## 2. 개발 백로그

### 🔴 P0 — 운영 안정성 (즉시 필요)

| # | 제목 | 설명 |
|---|------|------|
| 1 | 쿠키 만료 감지 및 사용자 안내 | NID_AUT/NID_SES 만료 시 스크래퍼가 조용히 실패함. 만료 감지 후 대시보드/로그에 명확한 경고 표시 필요 |
| 2 | 스크래퍼 재시도 로직 | 네트워크 오류, 타임아웃 시 즉시 실패 → 지수 백오프 재시도 필요 |
| 3 | 헬스체크 API 및 대시보드 상태 표시 | 마지막 스캔 성공/실패 여부, 스크래퍼 오류 횟수를 대시보드에서 확인 가능하게 |

### 🟡 P1 — 사용성 개선

| # | 제목 | 설명 |
|---|------|------|
| 4 | 키워드 관리 UI | config.py를 직접 수정하지 않고 대시보드에서 키워드 추가/삭제 가능하게 |
| 5 | 게시글 검색 기능 | 대시보드 내 제목·본문·작성자 텍스트 검색 |
| 6 | 통계 차트 시각화 | 일별/주별 탐지 건수 추이, 게시판별 비율 차트 |
| 7 | 모바일 반응형 UI | 스마트폰에서 대시보드 확인 가능하도록 반응형 레이아웃 |
| 8 | 게시글 내보내기 | 탐지된 게시글 목록을 CSV/Excel로 다운로드 |

### 🟢 P2 — 기능 확장

| # | 제목 | 설명 |
|---|------|------|
| 9 | AI 댓글 초안 자동 생성 | 탐지된 게시글 본문을 분석하여 댓글 초안을 Claude API로 생성, 담당자가 검토 후 수동 게시 |
| 10 | 제안서 초안 자동 생성 | 게시글 맥락 기반 커스터마이징된 제안서 초안(Markdown) 생성 |
| 11 | 멀티 카페 모니터링 | 현재 ak573 단일 카페 → 복수 카페 동시 모니터링 지원 |
| 12 | 대시보드 접근 인증 | 로컬 전용이지만, 외부 접근 차단을 위한 간단한 패스워드 인증 |

### ⚪ P3 — 품질/개발 환경

| # | 제목 | 설명 |
|---|------|------|
| 13 | 단위 테스트 작성 | scraper, db, api, uploader 모듈 단위 테스트 (pytest) |
| 14 | Docker 컨테이너화 | Windows 의존성 제거, 서버 배포 가능하도록 Docker 이미지 제공 |

---

## 3. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────┐
│  main.py (진입점)                                         │
│  ├── BackgroundScheduler (10분 간격 스캔)                 │
│  └── Flask Thread (웹서버 :5000)                          │
└──────────────────┬───────────────────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   scraper.py        │  ← Naver Cafe JSON API / HTML fallback
         │   (scan_all_boards) │    NID_AUT / NID_SES 쿠키 인증
         └─────────┬──────────┘
                   │ 탐지된 게시글
        ┌──────────▼──────────┐
        │   db.py (SQLite)     │  ← seen_posts (중복방지) + posts (대시보드)
        └──────────┬──────────┘
                   │
    ┌──────────────▼──────────────┐
    │         uploader.py          │  ← GitHub REST API
    │  (Markdown → GitHub 커밋)    │    posts/{board}/{YYYY-MM}/{id}_*.md
    └─────────────────────────────┘

    ┌─────────────────────────────┐
    │   api.py (Flask REST API)    │  ← GET/PATCH /api/posts
    │   web/index.html (대시보드)  │    30초 자동 갱신, 응대 상태 클릭 관리
    └─────────────────────────────┘
```

---

## 4. 데이터베이스 스키마

### `seen_posts` — 중복 탐지 방지
```sql
CREATE TABLE seen_posts (
    cafe_id    TEXT NOT NULL,
    article_id TEXT NOT NULL,
    menu_id    TEXT NOT NULL,
    title      TEXT,
    seen_at    TEXT,
    PRIMARY KEY (cafe_id, article_id)
);
```

### `posts` — 탐지 게시글 + 응대 상태 관리
```sql
CREATE TABLE posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cafe_id      TEXT NOT NULL,
    article_id   TEXT NOT NULL,
    menu_id      TEXT NOT NULL,
    board_name   TEXT NOT NULL,
    title        TEXT NOT NULL,
    author       TEXT,
    written_at   TEXT,
    content      TEXT,
    url          TEXT,
    keywords     TEXT,  -- JSON 배열
    status       TEXT DEFAULT 'pending',  -- pending|comment|proposal|done
    detected_at  TEXT NOT NULL,
    responded_at TEXT,
    UNIQUE(cafe_id, article_id)
);
```

---

## 5. API 명세

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/stats` | 대시보드 통계 (오늘/이달 건수, 응대율, 게시판별) |
| GET | `/api/posts` | 게시글 목록 (menu_id, status, limit, offset 필터) |
| GET | `/api/posts/<id>` | 게시글 상세 |
| PATCH | `/api/posts/<id>` | 응대 상태 변경 `{status: pending\|comment\|proposal\|done}` |
| GET | `/api/system` | 시스템 상태 (마지막/다음 스캔 시간, 폴링 주기) |
| GET | `/api/boards` | 게시판 목록 |

---

## 6. 환경변수 (.env)

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `NAVER_NID_AUT` | 네이버 NID_AUT 쿠키 (약 30일마다 갱신) | ✅ |
| `NAVER_NID_SES` | 네이버 NID_SES 쿠키 (약 30일마다 갱신) | ✅ |
| `GITHUB_TOKEN` | GitHub Personal Access Token (repo 권한) | ✅ |
| `GITHUB_USERNAME` | GitHub 사용자명 | ✅ |
| `GITHUB_REPO` | 저장 레포지토리명 (기본: naver-cafe-it-posts) | ✅ |
| `POLL_INTERVAL_MINUTES` | 스캔 주기 분 (기본: 10) | ❌ |

---

## 7. 로컬 개발 환경 세팅

```bash
# 1. 레포 클론
git clone https://github.com/kyeonghwan-tech/naver-cafe-monitor.git
cd naver-cafe-monitor

# 2. 가상환경 생성 및 의존성 설치
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일에 쿠키, GitHub 토큰 입력

# 4. 1회 테스트 실행
python main.py --once

# 5. 전체 실행 (스케줄러 + 웹서버)
python main.py --port 5000
# → http://localhost:5000 에서 대시보드 확인
```

---

## 8. 의존성

```
requests>=2.31.0        # HTTP 클라이언트
beautifulsoup4>=4.12.0  # HTML 파싱
python-dotenv>=1.0.0    # 환경변수 로드
apscheduler>=3.10.0     # 주기 실행 스케줄러
lxml>=5.0.0             # BeautifulSoup 파서
flask>=3.0.0            # 웹서버 + REST API
```

---

## 9. 제약사항 및 주의사항

- **네이버 쿠키:** NID_AUT / NID_SES는 약 30일마다 만료됨. 만료 시 .env에서 수동 갱신 필요
- **비공식 API:** `apis.naver.com/cafe-web/cafe2/ArticleListV2.json`은 공식 문서화되지 않은 내부 API. 네이버 정책 변경 시 `scraper.py` 수정 필요
- **PC 의존성:** Windows PC가 꺼져 있으면 모니터링 중단됨
- **`.env` 파일:** `.gitignore`에 포함됨. 절대 커밋하지 말 것
