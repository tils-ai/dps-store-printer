# 트러블슈팅

## GitHub Actions

### 1. actions must be pinned to a full-length commit SHA

**증상**: GitHub Actions 워크플로우 실행 시 아래 에러 발생
```
Error: The actions actions/checkout@v4, actions/setup-python@v5, and softprops/action-gh-release@v2
are not allowed because all actions must be pinned to a full-length commit SHA.
```

**원인**: org 정책에서 모든 actions를 태그(v4 등)가 아닌 커밋 SHA로 고정하도록 강제

**해결**: 태그 대신 커밋 SHA 사용
```yaml
# before
- uses: actions/checkout@v4

# after
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
```

### 2. Resource not accessible by integration (403)

**증상**: `softprops/action-gh-release`에서 Release 생성 시 403 에러
```
GitHub release failed with status: 403
{"message":"Resource not accessible by integration"}
```

**원인**: GitHub Actions의 기본 `GITHUB_TOKEN`에 Release 생성(contents write) 권한 없음

**해결**: 워크플로우에 `permissions` 추가
```yaml
permissions:
  contents: write

jobs:
  build:
    ...
```

### 3. poppler 경로를 못 찾아 --add-data 실패

**증상**: PyInstaller 빌드 시 에러
```
pyinstaller: error: argument --add-data: You have to specify both SOURCE and DEST
```
실제 실행된 명령: `--add-data ";poppler"` (SOURCE가 비어있음)

**원인**: `Get-ChildItem`으로 choco 설치 경로를 직접 탐색했으나 실제 경로가 달라서 `$popplerBin`이 빈 값

**해결**: choco 대신 MSYS2 pacman으로 poppler 설치. GitHub Actions windows-latest에 MSYS2가 기본 설치되어 있음.

시도한 방법들 (실패):
1. `choco install poppler` → tar 압축 해제 후 바이너리가 비어있음
2. `Get-Command pdftoppm` → choco가 PATH에 등록하지 않아 실패
3. GitHub releases에서 직접 다운로드 → URL이 유효하지 않음 (404)

최종 해결:
```powershell
C:\msys64\usr\bin\pacman.exe -S --noconfirm mingw-w64-x86_64-poppler
$popplerBin = "C:\msys64\mingw64\bin"
```

## 프로그램 실행

### 4. ZIP 파일 안정화 실패 (삭제됨?)

**증상**: ZIP 파일을 감시 폴더에 넣으면 즉시 안정화 실패 로그 출력
```
파일 안정화 실패 (삭제됨?): C:\...\접수증_2건.zip
```

**원인**: Windows에서 파일 복사 시 임시파일 생성 → rename 하는 경우가 있음. `on_created` 이벤트의 경로가 rename 후 사라짐

**해결**:
- `on_moved` 이벤트 추가 처리 (rename된 최종 파일 감지)
- 파일 미존재 시 즉시 실패하지 않고 최대 5초 재시도 대기
- 중복 처리 방지를 위한 `_processing` set 추가

### 5. poppler 미설치 에러 (PDFInfoNotInstalledError)

**증상**: PDF 처리 시 에러
```
pdf2image.exceptions.PDFInfoNotInstalledError: Unable to get page count. Is poppler installed and in PATH?
```

**원인**: exe 실행 환경에 poppler가 설치되어 있지 않음

**해결**: GitHub Actions 빌드 시 poppler 바이너리를 exe에 번들링 (`--add-data`), config.py에서 `sys._MEIPASS` 내 번들 경로 자동 탐색
