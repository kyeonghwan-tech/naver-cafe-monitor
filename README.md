# 네이버 카페 IT 교육 게시글 모니터

> 네이버 카페(ak573)에서 IT 교육 관련 게시글을 자동 탐지하고, GitHub에 아카이빙하며 웹 대시보드에서 영업 응대 현황을 관리하는 도구입니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🔍 **자동 탐지** | 4개 게시판을 10분마다 순회하여 IT 교육 키워드가 포함된 게시글 탐지 |
| 📤 **GitHub 아카이빙** | 탐지된 게시글을 Markdown으로 변환해 GitHub 레포에 자동 커밋 |
| 📊 **웹 대시보드** | 게시글 목록, 통계, 응대 상태를 브라우저에서 실시간 관리 |
| 🔄 **응대 상태 추적** | pending → comment → proposal → done 단계별 상태 관리 |
| 🖥️ **자동 시작** | Windows 로그인 시 자동 실행 (시작프로그램 등록) |

---

## 빠른 시작

### 1. 의존성 설치

```bash
python -m pip install -r requirements.txt
```

### 2. 환경 설정

`.env` 파일을 생성하고 아래 값을 입력합니다.

```env
NAVER_NID_AUT=<네이버 NID_AUT 쿠키>
NAVER_NID_SES=<네이버 NID_SES 쿠키>
GITHUB_TOKEN=<GitHub Personal Access Token>
GITHUB_USERNAME=<GitHub 사용자명>
GITHUB_REPO=naver-cafe-it-posts
```

> **쿠키 추출 방법**: Chrome 개발자 도구(F12) → Application → Cookies → `https://naver.com` → `NID_AUT`, `NID_SES` 값 복사

### 3. 실행

```bash
# 스케줄러 + 웹 대시보드 통합 실행 (권장)
python main.py

# 즉시 1회 스캔
python main.py --once

# 웹 서버 없이 스캔만 실행
python main.py --no-web

# 포트 변경
python main.py --port 8080
```

### 4. 대시보드 접속

브라우저에서 [http://localhost:5000](http://localhost:5000) 열기

---

## 모니터링 대상

**카페**: [ak573](https://cafe.naver.com/ak573) (카페 ID: 10733571)

| 게시판 | ID |
|--------|-----|
| 교육훈련 | 530 |
| 교육기획 | 14 |
| 강사추천 | 334 |
| 자유게시판 | 3 |

**탐지 키워드 예시**: AI, 인공지능, ChatGPT, LLM, 머신러닝, 딥러닝, 파이썬, 자동화, RPA, 디지털전환, 코딩교육, 데이터사이언스 등 40여 개

---

## 시스템 구조

```
사용자 PC (상시 실행)
│
├── APScheduler ─────────────────── 10분마다
│     └── scraper.py ────────────── 네이버 카페 API 수집
│           └── db.py ─────────────── SQLite 저장
│           └── uploader.py ───────── GitHub 커밋
│
└── Flask 웹서버 (:5000)
      └── web/index.html ─────────── 대시보드 UI
      └── api.py ─────────────────── REST API
```

자세한 아키텍처는 [ARCHITECTURE.md](./ARCHITECTURE.md)를 참고하세요.

---

## 대시보드 화면

| 영역 | 내용 |
|------|------|
| 통계 카드 | 오늘 탐지 건수, 미응대, 이번 달 합계, 응대율 |
| 게시글 목록 | 게시판 필터, 상태 필터, 최신순 정렬 |
| 응대 상태 | 클릭 한 번으로 상태 순환 변경 |
| 상세 모달 | 게시글 본문 + 원문 열기 링크 |
| 게시판 현황 | 게시판별 탐지 건수 차트 |

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/stats` | 통계 데이터 |
| GET | `/api/posts` | 게시글 목록 (`?menu_id=&status=&limit=&offset=`) |
| GET | `/api/posts/<id>` | 게시글 상세 |
| PATCH | `/api/posts/<id>` | 상태 변경 `{"status": "comment"}` |
| GET | `/api/system` | 마지막/다음 스캔 시간 |

---

## 프로젝트 문서

| 문서 | 설명 |
|------|------|
| [PRD.md](./PRD.md) | 제품 요구사항 문서 |
| [PLAN.md](./PLAN.md) | 개발 계획 및 GitHub 이슈 목록 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 (Mermaid 다이어그램 포함) |

---

## 기술 스택

- **Python 3.11+** — requests, BeautifulSoup4, APScheduler, Flask
- **SQLite 3** — WAL 모드, 중복 탐지 + 응대 상태 관리
- **Vanilla JS** — 30초 자동 갱신 대시보드
- **GitHub REST API** — 게시글 Markdown 아카이빙

---

## 라이선스

사내 전용 도구입니다.
