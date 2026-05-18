@echo off
echo === 라벨 프린터 자동 출력 프로그램 빌드 ===

REM 의존성 설치
pip install -r requirements.txt

REM PyInstaller로 exe 빌드 (단일 파일, watcher+agent 통합 GUI)
pyinstaller --onefile --name label-printer --windowed --hidden-import win32print --hidden-import win32ui --hidden-import win32api --hidden-import requests --hidden-import urllib3 --hidden-import certifi --hidden-import charset_normalizer --hidden-import idna --collect-data customtkinter --collect-submodules gui --add-data "assets/fonts;assets/fonts" main.py

echo.
echo 빌드 완료: dist\label-printer.exe
pause
