"""DB의 web-pc 오류 본문을 빈 문자열로 초기화"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

db.init_db()
conn = db.get_conn()
result = conn.execute(
    "UPDATE posts SET content='' WHERE content LIKE '%web-pc%'"
)
conn.commit()
print(f"완료: {result.rowcount}건 초기화")
