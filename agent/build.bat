@echo off
echo === 라벨 프린터 에이전트 빌드 ===

REM 의존성 설치
pip install -r requirements.txt

REM PyInstaller로 exe 빌드 (단일 파일, GUI 모드)
pyinstaller --onefile --name label-printer-agent --windowed --hidden-import win32print --hidden-import win32ui --hidden-import win32api --collect-data customtkinter main.py

echo.
echo 빌드 완료: dist\label-printer-agent.exe
pause
