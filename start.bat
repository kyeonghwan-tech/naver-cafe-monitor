@echo off
set PYTHONIOENCODING=utf-8
cd /d "C:\Users\user\OneDrive\문서\cdl\naver_cafe_monitor"

echo [1/4] Git pull...
git pull

echo [2/4] Playwright 설치...
python3 -m pip install playwright

echo [3/4] Chromium 설치...
python3 -m playwright install chromium

echo [4/4] 서버 시작...
python3 main.py --port 5000
