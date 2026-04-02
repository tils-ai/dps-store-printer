# CLAUDE.md - dps-store-printer

## 프로젝트 개요

DPS Store 접수증을 SLK TS200 감열 라벨 프린터로 자동 출력하는 Windows 프로그램 모음.
두 가지 모드로 동작한다.

- **watcher**: 감시 폴더에 PDF/ZIP 파일이 저장되면 자동으로 72mm 라벨에 맞게 변환하여 출력
- **agent**: store.dpl.shop API를 풀링하여 접수증 데이터를 받아 직접 PDF 생성 후 출력

## 기술 스택

- Python 3.11+
- watchdog (폴더 감시, watcher)
- pdf2image + poppler (PDF → 이미지 변환, watcher)
- requests (API 클라이언트, agent)
- Pillow (이미지 리사이즈/생성)
- pywin32 (Windows 프린터 출력)
- PyInstaller (.exe 빌드)

## 프로젝트 구조

```
watcher/                 # 폴더 감시 모드 (label-printer-watcher.exe)
├── main.py              # 진입점. 로깅 설정, 폴더 감시 시작
├── config.py            # 설정. exe 위치 기준 폴더 결정, config.ini 로드
├── config.ini           # 사용자 설정 파일
├── watcher.py           # watchdog 기반 폴더 감시
├── processor.py         # ZIP 해제, PDF→이미지 변환, 72mm 리사이즈
├── printer.py           # win32print/win32ui로 Windows 프린터 출력
├── requirements.txt
└── build.bat

agent/                   # API 풀링 모드 (label-printer-agent.exe)
├── main.py              # 진입점. 인증 + 풀링 루프
├── config.py            # 설정. API 키, 테넌트 등
├── config.ini           # 사용자 설정 파일
├── auth.py              # Device Auth 플로우 (브라우저 인증)
├── api_client.py        # store.dpl.shop API 클라이언트
├── receipt_builder.py   # JSON → 접수증 이미지 생성
├── printer.py           # Windows 프린터 출력
└── requirements.txt

.github/workflows/       # CI: 태그 push 시 두 exe 빌드 → Release 업로드
```

## 설계 문서

> 설계 문서는 **dps-store** 프로젝트에서 통합 관리합니다.
>
> - `dps-store/docs/print/20260310-label-printer-watcher-spec.md` — Watcher 설계
> - `dps-store/docs/print/20260310-label-printer-troubleshooting.md` — 트러블슈팅
> - `dps-store/docs/print/20260311-label-printer-agent-spec.md` — Agent 설계
> - `dps-store/docs/print/20260310-printer-client-api.md` — 서버 API 설계

## 빌드 & 배포

- `git tag vX.Y.Z && git push origin vX.Y.Z` → GitHub Actions가 Windows Runner에서 exe 빌드
- 결과물은 GitHub Releases에 업로드:
  - `label-printer-watcher.exe` + config.ini + 사용설명서.txt
  - `label-printer-agent.exe` + config.ini (agent 구현 후)
- GitHub Actions에서 actions는 반드시 **커밋 SHA로 고정**해야 함 (org 정책)

## 커밋 컨벤션

- `feat:` 새 기능
- `fix:` 버그 수정
- `docs:` 문서
- `ci:` CI/빌드 설정
- 한글 커밋 메시지 사용
- Co-Authored-By 문구 제외

## 주의사항

- pywin32는 Windows 전용 → macOS에서 테스트 불가
- watcher: poppler Windows 바이너리 필요 (exe에 번들링됨)
- agent: poppler 불필요 (Pillow로 직접 이미지 생성)
- 프린터명은 Windows 설정의 프린터 이름과 정확히 일치해야 함
