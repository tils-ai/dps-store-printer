# CLAUDE.md - equip-sync-l-module

## 프로젝트 개요

DPS Store 접수증을 SLK TS200 감열 라벨 프린터로 자동 출력하는 Windows 프로그램.
**Watcher + Agent 통합 단일 exe** (v3.0 이후).

- **Watcher**: 감시 폴더의 PDF/ZIP을 72mm 라벨에 맞게 변환하여 출력
- **Agent**: store.dpl.shop API를 풀링하여 접수증 데이터를 받아 직접 출력
- GUI는 단일 화면에서 Watcher/Agent 토글로 양쪽 모드를 제어

## 기술 스택

- Python 3.11+
- watchdog (폴더 감시)
- pdf2image + poppler (PDF → 이미지 변환)
- requests (API 클라이언트)
- Pillow (이미지 리사이즈/생성)
- pywin32 (Windows 프린터 출력)
- customtkinter (GUI)
- PyInstaller (.exe 빌드)

## 프로젝트 구조

```
watcher/                  # 통합 단일 진입점 (equip-sync-l.exe)
├── main.py               # 진입점
├── config.py             # config.ini 관리
├── auth.py               # Device Auth 플로우
├── api_client.py         # store.dpl.shop API 클라이언트
├── agent_worker.py       # API 풀링 루프
├── watcher.py            # watchdog 기반 폴더 감시
├── processor.py          # ZIP 해제, PDF→이미지 변환
├── receipt_builder.py    # JSON → 접수증 이미지 생성
├── printer.py            # win32print/win32ui로 Windows 프린터 출력
├── gui/                  # CustomTkinter GUI (Header / Cards / OpControl / Recent / LogBox / SettingsSlidePanel)
└── requirements.txt

.github/workflows/        # CI: 태그 push 시 단일 exe 빌드 → Release 업로드
```

## 설계 문서

> 설계 문서는 **dps-store** 프로젝트에서 통합 관리합니다.
>
> - `dps-store/docs/print/20260310-label-printer-watcher-spec.md` — Watcher 설계
> - `dps-store/docs/print/20260310-label-printer-troubleshooting.md` — 트러블슈팅
> - `dps-store/docs/print/20260311-label-printer-agent-spec.md` — Agent 설계
> - `dps-store/docs/print/20260310-printer-client-api.md` — 서버 API 설계

## 빌드 & 배포

- `git tag vX.Y.Z && git push origin vX.Y.Z` → GitHub Actions가 Windows Runner에서 단일 exe 빌드
- 결과물은 GitHub Releases에 업로드: `equip-sync-l-vX.Y.Z.exe` + GUIDE.txt
- GitHub Actions에서 actions는 반드시 **커밋 SHA로 고정**해야 함 (org 정책)

## 커밋 컨벤션

- `feat:` 새 기능
- `fix:` 버그 수정
- `docs:` 문서
- `ci:` CI/빌드 설정
- 한글 커밋 메시지 사용
- Co-Authored-By 문구 제외

## 주의사항

- pywin32는 Windows 전용 → macOS에서 테스트 불가 (win32 import는 호출 시점 지연)
- poppler Windows 바이너리 PyInstaller 번들 포함
- 프린터명은 Windows 설정의 프린터 이름과 정확히 일치해야 함
- config.ini / 로그 / 폴더는 **exe 옆 경로**에 자동 생성 (spec §11.5)
