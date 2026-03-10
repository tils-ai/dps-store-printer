# CLAUDE.md - dps-store-printer

## 프로젝트 개요

DPS Store 접수증(PDF)을 SLK TS200 감열 라벨 프린터로 자동 출력하는 Windows 프로그램.
감시 폴더에 PDF/ZIP 파일이 저장되면 자동으로 72mm 라벨에 맞게 변환하여 출력한다.

## 기술 스택

- Python 3.11+
- watchdog (폴더 감시)
- pdf2image + poppler (PDF → 이미지 변환)
- Pillow (이미지 리사이즈)
- pywin32 (Windows 프린터 출력)
- PyInstaller (.exe 빌드)

## 프로젝트 구조

```
main.py          # 진입점. 로깅 설정, 폴더 감시 시작, Ctrl+C 종료
config.py        # 설정. exe 위치 기준 폴더 결정, config.ini 로드
config.ini       # 사용자 설정 파일 (프린터명, DPI, poppler 경로)
watcher.py       # watchdog 기반 폴더 감시. 파일 크기 안정화 대기 후 처리
processor.py     # ZIP 해제, PDF→이미지 변환, 72mm 리사이즈, done/error 이동
printer.py       # win32print/win32ui로 Windows 프린터 출력
build.bat        # Windows에서 PyInstaller exe 빌드 스크립트
.github/workflows/build.yml  # GitHub Actions: 태그 push 시 Windows exe 빌드 → Release 업로드
```

## 빌드 & 배포

- `git tag vX.Y.Z && git push origin vX.Y.Z` → GitHub Actions가 Windows Runner에서 exe 빌드
- 결과물은 GitHub Releases에 `label-printer-watcher.exe`로 업로드됨
- GitHub Actions에서 actions는 반드시 **커밋 SHA로 고정**해야 함 (org 정책)

## 실행 방식

exe를 원하는 폴더에 놓고 실행하면 같은 위치에 `watch/`, `done/`, `error/` 폴더 자동 생성.
`config.ini`를 exe 옆에 두면 프린터명, DPI, poppler 경로 설정 가능.

## 커밋 컨벤션

- `feat:` 새 기능
- `fix:` 버그 수정
- `docs:` 문서
- `ci:` CI/빌드 설정
- 한글 커밋 메시지 사용
- Co-Authored-By 문구 제외

## 주의사항

- pywin32는 Windows 전용 → macOS에서 테스트 불가
- poppler Windows 바이너리 별도 설치 필요
- 프린터명은 Windows 설정의 프린터 이름과 정확히 일치해야 함
