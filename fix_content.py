"""DB에 저장된 web-pc 메시지 본문을 빈 문자열로 초기화"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "monitor.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("""
    UPDATE posts
    SET content = ''
    WHERE content LIKE "%web-pc doesn't work properly%"
""")
print(f"수정된 게시글: {cur.rowcount}건")
conn.commit()
conn.close()
