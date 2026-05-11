# CLAUDE.md - equip-sync-l-module (라벨/접수증 프린터)

이 레포의 Claude 컨텍스트와 설계 문서는 **`dps-store`** 프로젝트에서 통합 관리한다.

- dps-store 로컬 경로: `~/Workspace/dps-store`
- 외부 레포 테이블·통합 정책: `dps-store/CLAUDE.md` 의 "관련 외부 레포" 섹션
- 관련 설계 문서: `dps-store/docs/print/*` (라벨/접수증 모듈은 `20260310-label-printer-*.md`, `20260311-label-printer-agent-spec.md`, `20260310-printer-client-api.md`, `20260511-equipment-gui-*.md`)

이 레포 단독 작업 시에도 위 문서를 우선 참조하라.

## 간단 정리 (메모)

- SLK TS200 감열 라벨 프린터로 DPS Store 접수증 자동 출력 (Windows)
- Watcher + Agent 통합 단일 exe (v3.0 이후, PyInstaller)
- 빌드 산출물: `equip-sync-l-vX.Y.Z.exe` (태그 push 시 GitHub Actions에서 자동 빌드)
- config.ini / 폴더(watch/done/error) / 로그는 **exe 옆 경로**에 자동 생성 (spec §11.5)
- poppler Windows 바이너리는 PyInstaller 번들에 포함
