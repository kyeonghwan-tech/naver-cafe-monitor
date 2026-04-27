from config import NAVER_COOKIES
print("NID_AUT:", NAVER_COOKIES.get("NID_AUT", "없음")[:20])
print("NID_SES:", NAVER_COOKIES.get("NID_SES", "없음")[:20])
