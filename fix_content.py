"""
기존 DB의 web-pc 오류 본문을 Playwright로 재수집
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from scraper import fetch_article_content

db.init_db()
conn = db.get_conn()

# web-pc 메시지가 있는 게시글 조회
rows = conn.execute(
    "SELECT article_id FROM posts WHERE content LIKE '%web-pc%' OR content = ''"
).fetchall()

print(f"재수집 대상: {len(rows)}건")
updated = 0
for (article_id,) in rows:
    content = fetch_article_content(article_id)
    if content and "web-pc" not in content:
        conn.execute("UPDATE posts SET content=? WHERE article_id=?", (content, article_id))
        conn.commit()
        updated += 1
        print(f"  ✓ {article_id}: {content[:50]}")
    else:
        print(f"  ✗ {article_id}: 여전히 빈 본문")

print(f"\n완료: {updated}/{len(rows)}건 업데이트")
