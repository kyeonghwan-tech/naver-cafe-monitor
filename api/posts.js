/**
 * GET /api/posts          - 게시글 목록 (네이버 카페 실시간 스크래핑)
 * GET /api/posts?menu_id= - 특정 게시판만
 */

const CAFE_ID = "10733571";

const BOARDS = [
  { id: "530", name: "교육훈련" },
  { id: "14",  name: "교육기획" },
  { id: "334", name: "강사추천" },
  { id: "3",   name: "자유게시판" },
];

const IT_KEYWORDS = [
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
];

const HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  "Referer": "https://cafe.naver.com/",
  "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
};

function matchKeywords(title) {
  const lower = title.toLowerCase();
  return IT_KEYWORDS.filter((kw) => lower.includes(kw.toLowerCase()));
}

function getBoardName(menuId) {
  const board = BOARDS.find((b) => b.id === menuId);
  return board ? board.name : menuId;
}

function makeCookieHeader() {
  const aut = process.env.NAVER_NID_AUT || "";
  const ses = process.env.NAVER_NID_SES || "";
  if (aut && ses) {
    return `NID_AUT=${aut}; NID_SES=${ses}`;
  }
  return "";
}

async function fetchBoardJson(menuId, perPage = 20) {
  const cookie = makeCookieHeader();
  const params = new URLSearchParams({
    "search.clubid": CAFE_ID,
    "search.menuid": menuId,
    "search.page": "1",
    "search.perPage": String(perPage),
    "search.boardtype": "L",
    "userType": "",
  });

  const url = `https://apis.naver.com/cafe-web/cafe2/ArticleListV2.json?${params}`;
  const headers = { ...HEADERS };
  if (cookie) headers["Cookie"] = cookie;

  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const data = await resp.json();
  const items = data?.message?.result?.articleList || [];
  if (!items.length) throw new Error("empty articleList");

  const boardName = getBoardName(menuId);
  return items.map((item) => {
    const aid = String(item.articleId || "");
    const title = item.subject || "";
    return {
      article_id: aid,
      title,
      author: item.writerNickname || "",
      written_at: String(item.writeDateTimestamp || ""),
      menu_id: menuId,
      board_name: boardName,
      keywords: matchKeywords(title),
      status: "pending",
      url: `https://cafe.naver.com/ArticleRead.nhn?clubid=${CAFE_ID}&articleid=${aid}`,
      content: "",
    };
  });
}

async function fetchBoardHtml(menuId, perPage = 20) {
  const cookie = makeCookieHeader();
  const params = new URLSearchParams({
    "search.clubid": CAFE_ID,
    "search.menuid": menuId,
    "search.page": "1",
    "search.perPage": String(perPage),
    "search.boardtype": "L",
  });

  const url = `https://cafe.naver.com/ArticleList.nhn?${params}`;
  const headers = { ...HEADERS };
  if (cookie) headers["Cookie"] = cookie;

  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(`HTML fetch HTTP ${resp.status}`);

  const html = await resp.text();
  const boardName = getBoardName(menuId);
  const articles = [];

  // article id + title 파싱 (정규식)
  const rowRegex = /articleid=(\d+)[^"]*"[^>]*class="[^"]*article[^"]*"[^>]*>([^<]+)</g;
  let m;
  while ((m = rowRegex.exec(html)) !== null) {
    const aid = m[1];
    const title = m[2].trim();
    if (!title) continue;
    articles.push({
      article_id: aid,
      title,
      author: "",
      written_at: "",
      menu_id: menuId,
      board_name: boardName,
      keywords: matchKeywords(title),
      status: "pending",
      url: `https://cafe.naver.com/ArticleRead.nhn?clubid=${CAFE_ID}&articleid=${aid}`,
      content: "",
    });
  }
  return articles;
}

async function fetchBoard(menuId) {
  // 1차: JSON API
  try {
    const posts = await fetchBoardJson(menuId);
    if (posts.length > 0) return posts;
  } catch (e) {
    console.warn(`[posts] JSON API failed (menu ${menuId}):`, e.message);
  }

  // 2차: HTML fallback
  try {
    const posts = await fetchBoardHtml(menuId);
    return posts;
  } catch (e) {
    console.error(`[posts] HTML fallback failed (menu ${menuId}):`, e.message);
    return [];
  }
}

export default async function handler(req, res) {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");

  if (req.method === "OPTIONS") {
    return res.status(204).end();
  }

  const { menu_id, status } = req.query;

  try {
    const boardsToScan = menu_id
      ? BOARDS.filter((b) => b.id === menu_id)
      : BOARDS;

    const results = await Promise.all(
      boardsToScan.map((b) => fetchBoard(b.id))
    );
    let allPosts = results.flat();

    if (status) {
      allPosts = allPosts.filter((p) => p.status === status);
    }

    return res.status(200).json(allPosts);
  } catch (e) {
    console.error("[posts] handler error:", e);
    return res.status(500).json({ error: e.message });
  }
}
