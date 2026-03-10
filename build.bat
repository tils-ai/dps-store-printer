@echo off
echo === 라벨 프린터 자동 출력 프로그램 빌드 ===

REM 의존성 설치
pip install -r requirements.txt

REM PyInstaller로 exe 빌드 (단일 파일)
pyinstaller --onefile --name label-printer-watcher --console main.py

echo.
echo 빌드 완료: dist\label-printer-watcher.exe
echo.
echo [주의] poppler 바이너리를 별도로 설치하고 PATH에 추가하거나
echo       POPPLER_PATH 환경변수를 설정해야 합니다.
pause
