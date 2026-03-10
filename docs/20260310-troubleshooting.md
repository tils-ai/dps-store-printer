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
