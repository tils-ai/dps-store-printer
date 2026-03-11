@echo off
pyinstaller --onefile --name label-printer-agent --console --hidden-import win32print --hidden-import win32ui --hidden-import win32api main.py
echo 빌드 완료: dist\label-printer-agent.exe
pause
