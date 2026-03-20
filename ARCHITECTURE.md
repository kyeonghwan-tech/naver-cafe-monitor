# 아키텍처 문서 — 네이버 카페 IT 교육 게시글 모니터

> 버전: 1.0 · 최종 수정: 2026-03-20

---

## 1. 시스템 개요

네이버 카페(ak573)의 4개 게시판을 10분마다 자동 순회하여 **IT 교육 관련 키워드**가 포함된 게시글을 탐지하고, GitHub에 마크다운으로 아카이빙한 뒤 웹 대시보드에서 영업팀이 응대 상태를 추적할 수 있는 모니터링 시스템입니다.

---

## 2. 전체 시스템 아키텍처

```mermaid
graph TB
    subgraph External["외부 서비스"]
        NC["☁️ 네이버 카페\napis.naver.com"]
        GH["☁️ GitHub API\napi.github.com"]
    end

    subgraph App["Python 애플리케이션 (main.py)"]
        direction TB
        SCH["⏰ APScheduler\nBackgroundScheduler\n10분 간격"]
        SCN["🔍 Scraper\nscraper.py"]
        UPL["📤 Uploader\nuploader.py"]
        DB[("🗄️ SQLite DB\nseen_posts.db")]
        API["🌐 Flask API\napi.py\n:5000"]
        WEB["📊 Web Dashboard\nweb/index.html"]
    end

    subgraph Config["설정"]
        ENV[".env\nCookies / Tokens"]
        CFG["config.py\nKeywords / Boards"]
    end

    SCH -->|"매 10분"| SCN
    SCN -->|"쿠키 인증"| NC
    NC -->|"게시글 목록+본문"| SCN
    SCN -->|"키워드 매칭 후 저장"| DB
    SCN -->|"신규 게시글"| UPL
    UPL -->|"Markdown 커밋"| GH
    DB -->|"조회/상태 업데이트"| API
    API -->|"정적 파일 서빙"| WEB
    ENV --> SCN
    ENV --> UPL
    CFG --> SCN
    CFG --> API

    style External fill:#f0f4ff,stroke:#6b7fff
    style App fill:#f0fff4,stroke:#34d399
    style Config fill:#fffbf0,stroke:#f59e0b
```

---

## 3. 컴포넌트별 상세

### 3-1. 진입점 — `main.py`

```mermaid
flowchart TD
    A[python main.py] --> B{--once 옵션?}
    B -- Yes --> C[run_scan 1회 실행] --> Z[종료]
    B -- No --> D{--no-web 옵션?}
    D -- No --> E[Flask 웹서버\n백그라운드 스레드 시작]
    D -- Yes --> F[스케줄러 시작]
    E --> F
    F --> G[즉시 run_scan 1회]
    G --> H[⏰ 10분 간격 반복 스캔]
    H --> I[KeyboardInterrupt?]
    I -- Yes --> J[scheduler.shutdown] --> Z
    I -- No --> H
```

**CLI 옵션**

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--once` | false | 즉시 1회 스캔 후 종료 |
| `--no-web` | false | 웹 서버 없이 스캔만 실행 |
| `--port` | 5000 | 웹 서버 포트 |
| `--interval` | 10 | 폴링 주기(분) |

---

### 3-2. 스크래퍼 — `scraper.py`

```mermaid
sequenceDiagram
    participant SCH as APScheduler
    participant SCN as scraper.py
    participant NAV as Naver API
    participant NAV2 as Naver HTML
    participant DB as SQLite (db.py)

    SCH->>SCN: scan_all_boards()
    loop 4개 게시판
        SCN->>NAV: GET ArticleListV2.json<br/>(NID_AUT, NID_SES 쿠키)
        alt JSON 성공
            NAV-->>SCN: 게시글 목록 JSON
        else JSON 실패 / 401
            SCN->>NAV2: GET cafe.naver.com/ArticleRead.nhn
            NAV2-->>SCN: HTML 파싱 (BeautifulSoup)
        end
        loop 각 게시글
            SCN->>DB: is_seen(article_id)?
            alt 미탐지
                SCN->>NAV: 본문 조회
                SCN->>SCN: IT 키워드 매칭
                alt 키워드 일치
                    SCN->>DB: save_post()
                    SCN->>DB: mark_seen()
                end
            end
        end
    end
    SCN-->>SCH: matched_articles[]
```

**모니터링 게시판**

| 게시판 ID | 게시판 이름 |
|-----------|-------------|
| 530 | 교육훈련 |
| 14 | 교육기획 |
| 334 | 강사추천 |
| 3 | 자유게시판 |

---

### 3-3. 데이터베이스 — `db.py`

```mermaid
erDiagram
    seen_posts {
        TEXT cafe_id PK
        TEXT article_id PK
        TEXT menu_id
        TEXT title
        TEXT seen_at
    }

    posts {
        INTEGER id PK
        TEXT cafe_id
        TEXT article_id UK
        TEXT menu_id
        TEXT board_name
        TEXT title
        TEXT author
        TEXT written_at
        TEXT content
        TEXT url
        TEXT keywords
        TEXT status
        TEXT detected_at
        TEXT responded_at
    }
```

**응대 상태(status) 흐름**

```mermaid
stateDiagram-v2
    [*] --> pending : 게시글 탐지
    pending --> comment : 댓글 작성
    comment --> proposal : 제안서 발송
    proposal --> done : 계약 완료
    pending --> done : 직접 완료
    comment --> done : 직접 완료
```

---

### 3-4. GitHub 업로더 — `uploader.py`

```mermaid
flowchart LR
    A[신규 게시글] --> B{레포 존재?}
    B -- No --> C[GitHub API\n레포 자동 생성]
    C --> D
    B -- Yes --> D[파일 경로 생성\nboards/게시판명/YYYYMMDD_제목.md]
    D --> E[파일 존재 확인\nGET /contents/path]
    E -- 존재 --> F[SHA 추출 → UPDATE]
    E -- 없음 --> G[신규 CREATE]
    F --> H[✅ 커밋 완료]
    G --> H
```

---

### 3-5. REST API — `api.py`

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/` | 대시보드 HTML 서빙 |
| `GET` | `/api/stats` | 오늘/이번달 통계, 게시판별 현황 |
| `GET` | `/api/posts` | 게시글 목록 (필터: menu_id, status) |
| `GET` | `/api/posts/<id>` | 게시글 상세 |
| `PATCH` | `/api/posts/<id>` | 응대 상태 변경 |
| `GET` | `/api/system` | 마지막/다음 스캔 시간 |

---

### 3-6. 웹 대시보드 — `web/index.html`

```mermaid
graph LR
    subgraph Browser["브라우저 (Vanilla JS)"]
        UI["📊 대시보드 UI"]
        TIMER1["⏱️ 30초 자동 갱신\n(게시글 목록)"]
        TIMER2["⏱️ 5초 자동 갱신\n(시스템 상태)"]
    end

    subgraph Features["주요 기능"]
        STAT["📈 통계 카드\n오늘/이번달/응대율"]
        LIST["📋 게시글 목록\n필터/정렬"]
        STATUS["🔄 응대 상태 관리\npending→comment→proposal→done"]
        MODAL["🔍 상세 모달\n원문 열기 ↗"]
        BOARD["📌 게시판별 현황"]
    end

    UI --> STAT
    UI --> LIST
    UI --> STATUS
    UI --> MODAL
    UI --> BOARD
    TIMER1 --> LIST
    TIMER2 --> STAT
```

---

## 4. 데이터 흐름 전체

```mermaid
flowchart TD
    A["☁️ 네이버 카페\n(ak573)"] -->|"HTTP GET\n쿠키 인증"| B["🔍 scraper.py\n게시글 목록·본문 수집"]
    B -->|"IT 키워드 매칭"| C{매칭?}
    C -- No --> D["🔲 is_seen 기록만"]
    C -- Yes --> E["🗄️ SQLite\nposts 저장"]
    E --> F["📤 uploader.py\nMarkdown 변환"]
    F -->|"REST API"| G["☁️ GitHub\nnaver-cafe-it-posts 레포"]
    E --> H["🌐 Flask API\n/api/posts"]
    H --> I["📊 웹 대시보드\nlocalhost:5000"]
    I -->|"PATCH /api/posts/:id"| H
    H -->|"status 업데이트"| E
```

---

## 5. 배포 구조

```mermaid
graph TB
    subgraph Windows["Windows PC (상시 실행)"]
        BAT["▶️ start.bat\n(시작프로그램 등록)"]
        PROC["Python 프로세스\nmain.py"]
        DB2[("SQLite\ndata/seen_posts.db")]
        LOG["📝 monitor.log"]
    end

    BAT -->|"PC 시작 시 자동 실행"| PROC
    PROC --> DB2
    PROC --> LOG
    PROC -->|":5000"| DASH["📊 대시보드\nhttp://localhost:5000"]
    PROC -->|"매 10분"| NAV["☁️ 네이버 카페"]
    PROC -->|"신규 게시글"| GIT["☁️ GitHub"]
```

---

## 6. 설정 파일

### `.env`

```env
NAVER_NID_AUT=<네이버 인증 쿠키>
NAVER_NID_SES=<네이버 세션 쿠키>
GITHUB_TOKEN=<GitHub Personal Access Token>
GITHUB_USERNAME=<GitHub 사용자명>
GITHUB_REPO=naver-cafe-it-posts
POLL_INTERVAL_MINUTES=10   # 선택, 기본 10분
```

### `config.py` 주요 상수

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `CAFE_ID` | `10733571` | 모니터링 대상 카페 ID |
| `POLL_INTERVAL_MINUTES` | `10` | 스캔 주기(분) |
| `IT_KEYWORDS` | 40여 개 | 탐지 키워드 목록 |

---

## 7. 기술 스택

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 스케줄러 | APScheduler 3.x (BackgroundScheduler) |
| HTTP 클라이언트 | requests + BeautifulSoup4 |
| 웹 프레임워크 | Flask 3.x |
| 데이터베이스 | SQLite 3 (WAL 모드) |
| 프론트엔드 | Vanilla JS (ES2022), CSS Grid/Flexbox |
| 외부 연동 | Naver Cafe Internal API, GitHub REST API v3 |
| 실행 환경 | Windows 11, 시작프로그램 BAT 자동 실행 |

---

## 8. 디렉토리 구조

```
naver_cafe_monitor/
├── main.py           # 진입점 — 스케줄러 + Flask 통합 실행
├── config.py         # 환경변수 로드, 키워드/게시판 설정
├── scraper.py        # 네이버 카페 스크래핑 (JSON API + HTML fallback)
├── db.py             # SQLite 데이터 레이어
├── api.py            # Flask REST API
├── uploader.py       # GitHub 마크다운 업로더
├── web/
│   └── index.html    # 웹 대시보드 (SPA)
├── mockup/
│   └── index.html    # 초기 UI 목업 (참고용)
├── data/
│   └── seen_posts.db # SQLite 데이터베이스
├── .env              # 비밀 설정 (git 제외)
├── requirements.txt  # Python 의존성
├── start.bat         # Windows 실행 스크립트
├── monitor.log       # 실행 로그
├── PRD.md            # 제품 요구사항 문서
├── PLAN.md           # 개발 계획 문서
└── ARCHITECTURE.md   # 현재 파일
```
