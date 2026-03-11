# 라벨 프린터 API 에이전트 (label-printer-agent)

> 작성일: 2026-03-11

## 개요

store.dpl.shop API를 풀링하여 접수증 데이터를 수신하고, Pillow로 접수증 이미지를 직접 생성하여 감열 프린터로 출력하는 Windows 프로그램.

기존 `watcher`(폴더 감시 모드)와 별도 exe로 빌드되며, poppler 의존성 없이 동작한다.

### watcher와의 차이

| 항목 | watcher | agent |
|------|---------|-------|
| 데이터 소스 | 로컬 폴더 (PDF/ZIP) | store.dpl.shop API (JSON) |
| PDF 처리 | pdf2image + poppler | 불필요 |
| 이미지 생성 | PDF에서 변환 | Pillow로 직접 그림 |
| 인증 | 없음 | Device Auth → API Key |
| 트리거 | 파일 생성 이벤트 | HTTP 풀링 (주기적) |
| 의존성 | watchdog, pdf2image, poppler | requests, Pillow |

## 환경

- **OS**: Windows
- **Python**: 3.11+
- **프린터**: SLK TS200 (감열 라벨 프린터, USB, 드라이버 설치 완료)
- **라벨 규격**: 폭 72mm (config.ini의 receiptWidthMm에 따라 58/72/80mm 대응)
- **서버**: store.dpl.shop (HTTPS)

## 핵심 흐름

```
최초 실행 (API 키 없음)
  ↓
Device Auth: 인증 요청 → 브라우저 승인 → API 키 발급 → config.ini에 저장
  ↓
풀링 루프 시작
  ↓
GET /api/printer/receipts (Authorization: Bearer pk_...)
  ├─ 빈 응답 → 대기 (서버 pollInterval 우선, 없으면 adaptive 백오프)
  └─ receipts 있음 → 간격 복원
       ↓
     접수증 JSON → Pillow로 이미지 생성
       ├─ dualCopy: true → "매장용"/"고객용" 2장 생성
       └─ dualCopy: false → 1장 생성
       ↓
     프린터 출력 (win32print)
       ├─ 성공 → POST /api/printer/receipts/{id}/printed
       └─ 실패 → POST /api/printer/receipts/{id}/failed
```

## 디렉토리 구조

```
agent/
├── main.py              # 진입점: 인증 확인 → 풀링 루프
├── config.py            # 설정: config.ini 로드, API 키 저장
├── config.ini           # 사용자 설정 파일
├── auth.py              # Device Auth 플로우 (브라우저 인증)
├── api_client.py        # store.dpl.shop API 클라이언트
├── receipt_builder.py   # JSON → 접수증 이미지 생성 (Pillow)
├── printer.py           # Windows 프린터 출력 (watcher/printer.py 복사)
├── requirements.txt
└── build.bat
```

## 모듈별 상세

### config.py — 설정 관리

```python
# config.ini에서 로드하는 값
PRINTER_NAME   = "SLK TS200"     # [printer] name
PRINTER_DPI    = 203             # [printer] dpi
RENDER_DPI     = 300             # [printer] render_dpi

API_TENANT     = ""              # [api] tenant
API_KEY        = ""              # [api] api_key (인증 후 자동 기록)
BASE_URL       = "https://store.dpl.shop"  # [api] base_url
POLL_INTERVAL  = 5               # [api] poll_interval (초)
```

**추가 함수:**

```python
def save_api_key(api_key: str):
    """인증 성공 후 API 키를 config.ini [api] 섹션에 기록."""
    _ini.set("api", "api_key", api_key)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)
```

### config.ini

```ini
[printer]
name = SLK TS200
dpi = 203
render_dpi = 300

[api]
tenant = musinsa
api_key =
base_url = https://store.dpl.shop
poll_interval = 5
```

### auth.py — Device Auth 플로우

서버의 Device Auth API를 호출하여 API 키를 발급받는다.

```
1. POST /api/printer/auth/request  { tenant: "musinsa" }
   → { deviceCode, userCode, verifyUrl, expiresIn }

2. 콘솔에 URL + 인증 코드 표시, webbrowser.open()으로 브라우저 자동 오픈

3. 2초 간격으로 POST /api/printer/auth/poll  { deviceCode }
   → "pending" | "approved" (apiKey 포함) | "expired"

4. 승인되면 api_key를 반환
```

**에러 처리:**
- 네트워크 오류: 재시도 안내 후 종료
- 테넌트 없음 (404): "config.ini의 tenant 설정을 확인하세요" 출력
- 요청 제한 (429): "잠시 후 다시 시도하세요" 출력
- 만료 (410): "인증 시간이 만료되었습니다. 프로그램을 다시 실행하세요" 출력

### api_client.py — API 클라이언트

```python
VERSION = "1.0.0"

class PrinterApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers["X-Client-Version"] = VERSION
        self.base_url = base_url

    def get_pending_receipts(self, limit: int = 10) -> tuple[list[dict], int | None]:
        """미출력 접수증 조회. 서버가 PENDING→PRINTING으로 선점.
        Returns: (receipts, pollInterval)
          - pollInterval: 서버가 지정한 다음 풀링 간격(초). 없으면 None.
        """
        resp = self.session.get(
            f"{self.base_url}/api/printer/receipts",
            params={"status": "pending", "limit": limit},
        )
        if resp.status_code == 426:
            raise UpgradeRequiredError(resp.json())
        if resp.status_code == 401:
            raise AuthExpiredError("API 키가 만료되었습니다.")
        resp.raise_for_status()
        data = resp.json()
        return data["receipts"], data.get("pollInterval")

    def mark_printed(self, receipt_id: str):
        """출력 완료 보고."""
        resp = self.session.post(
            f"{self.base_url}/api/printer/receipts/{receipt_id}/printed"
        )
        resp.raise_for_status()

    def mark_failed(self, receipt_id: str, reason: str = ""):
        """출력 실패 보고."""
        resp = self.session.post(
            f"{self.base_url}/api/printer/receipts/{receipt_id}/failed",
            json={"reason": reason} if reason else None,
        )
        resp.raise_for_status()
```

**커스텀 예외:**

```python
class UpgradeRequiredError(Exception):
    """서버가 클라이언트 업데이트를 요구 (426)."""
    pass

class AuthExpiredError(Exception):
    """API 키가 만료/해제됨 (401)."""
    pass
```

### receipt_builder.py — 접수증 이미지 생성

Pillow로 감열 프린터용 접수증 이미지를 직접 생성한다. 서버에서 받은 JSON 데이터를 그대로 렌더링.

**입력:** 서버 응답의 receipt 객체

```python
{
  "id": "...",
  "orderNumber": "20260311-000001",
  "createdAt": "2026-03-11T14:30:00Z",
  "brandName": "무신사",
  "recipientName": "홍*동",       # 이미 마스킹됨
  "contact": "010-****-5678",     # 이미 마스킹됨
  "items": [
    { "productName": "티셔츠", "optionName": "화이트 / L", "quantity": 2, "totalPrice": 40000 }
  ],
  "itemsTotal": 40000,
  "shippingAmount": 3000,
  "discountAmount": 0,
  "totalAmount": 43000,
  "paymentMethod": "현장결제",
  "paymentStatus": "결제 완료",
  "receiptWidthMm": 72,
  "dualCopy": true
}
```

**출력:** Pillow Image 객체 (1장 또는 2장)

**레이아웃:**

```
┌────────────────────────────────┐
│          [매장용]               │  ← dualCopy 시에만 표시
│                                │
│        ★ 무신사 ★              │  ← 브랜드명 (가운데 정렬, 볼드)
│────────────────────────────────│
│  주문번호  20260311-000001     │
│  일시      2026.03.11 14:30    │
│  수령인    홍*동                │
│  연락처    010-****-5678       │
│────────────────────────────────│
│  티셔츠                        │
│    화이트 / L × 2    40,000원  │
│────────────────────────────────│
│  상품금액          40,000원    │
│  배송비             3,000원    │
│  총 결제금액       43,000원    │  ← 볼드
│────────────────────────────────│
│  현장결제 / 결제 완료          │
└────────────────────────────────┘
```

**함수 시그니처:**

```python
def build_receipt_images(
    receipt: dict,
    printer_dpi: int = 203,
) -> list[Image.Image]:
    """
    접수증 이미지를 생성한다.
    dualCopy=True이면 [매장용, 고객용] 2장, False이면 [접수증] 1장 반환.
    """
```

**구현 전략:**

1. `receiptWidthMm`과 `printer_dpi`로 이미지 폭(px) 계산
2. 임시로 높이 2000px 캔버스 생성 → 텍스트를 그리며 y 좌표 누적
3. 최종 y 좌표로 이미지를 crop하여 정확한 높이 결정
4. dualCopy 시 동일 로직을 copyLabel만 바꿔 2회 실행

**폰트:**

- Windows 기본 한글 폰트 사용: `C:/Windows/Fonts/malgun.ttf` (맑은 고딕)
- 폰트 없으면 `C:/Windows/Fonts/gulim.ttc` 폴백
- 크기: 브랜드명 24pt, 본문 16pt, 합계 18pt (DPI에 따라 비례 조정)

**금액 포맷:**

```python
def format_price(amount: int) -> str:
    return f"{amount:,}원"
```

### printer.py — Windows 프린터 출력

watcher/printer.py와 동일한 로직. `print_image()`, `print_images()` 함수를 그대로 사용한다.

### main.py — 진입점

```python
def main():
    # 1. API 키 확인
    if not config.API_KEY:
        if not config.API_TENANT:
            print("config.ini의 [api] tenant를 설정해주세요.")
            input("아무 키나 누르면 종료...")
            return
        # Device Auth 실행
        api_key = authenticate(config.API_TENANT)
        config.save_api_key(api_key)

    # 2. API 클라이언트 생성
    client = PrinterApiClient(config.BASE_URL, config.API_KEY)

    # 3. 풀링 루프
    start_polling(client)
```

**풀링 루프 (start_polling):**

```python
def start_polling(client: PrinterApiClient):
    empty_count = 0  # 빈 응답 연속 횟수 (백오프용)

    while True:
        try:
            receipts, server_interval = client.get_pending_receipts()

            if not receipts:
                empty_count += 1
                # 서버 지정 간격 우선, 없으면 클라이언트 백오프
                interval = server_interval or _backoff_interval(empty_count)
                time.sleep(interval)
                continue

            empty_count = 0  # 데이터 수신 시 리셋

            for receipt in receipts:
                process_receipt(client, receipt)

            interval = server_interval or config.POLL_INTERVAL
            time.sleep(interval)

        except AuthExpiredError:
            logger.error("API 키가 만료되었습니다. 프로그램을 다시 실행하여 재인증하세요.")
            config.save_api_key("")  # 키 삭제
            break

        except UpgradeRequiredError as e:
            logger.error("클라이언트 업데이트가 필요합니다: %s", e)
            break

        except requests.ConnectionError:
            logger.warning("네트워크 연결 실패. 30초 후 재시도...")
            time.sleep(30)

        except Exception:
            logger.exception("풀링 중 예외 발생. 10초 후 재시도...")
            time.sleep(10)
```

**접수증 처리 (process_receipt):**

```python
def process_receipt(client: PrinterApiClient, receipt: dict):
    receipt_id = receipt["id"]
    try:
        images = build_receipt_images(receipt, config.PRINTER_DPI)
        for img in images:
            print_image(img)
        client.mark_printed(receipt_id)
        logger.info("출력 완료: %s", receipt["orderNumber"])

    except Exception as e:
        logger.exception("출력 실패: %s", receipt["orderNumber"])
        try:
            client.mark_failed(receipt_id, str(e))
        except Exception:
            logger.exception("실패 보고 오류")
```

**풀링 간격 우선순위:**

1. **서버 응답의 `pollInterval`** — 서버가 지정하면 무조건 따름
2. **클라이언트 adaptive 백오프** — 서버 미지정 시 빈 응답 횟수에 따라 증가

```python
def _backoff_interval(empty_count: int) -> float:
    """빈 응답 연속 횟수에 따른 풀링 간격 (서버 미지정 시 폴백)."""
    if empty_count < 3:
        return config.POLL_INTERVAL      # 5초
    if empty_count < 6:
        return 10
    if empty_count < 10:
        return 20
    return 30  # 최대 30초
```

서버에서 `pollInterval: 5`를 항상 내려주면 백오프 없이 고정 5초 간격으로 동작한다.

## config.ini 전체

```ini
[printer]
; Windows 설정 > 프린터에서 정확한 이름 확인
name = SLK TS200
dpi = 203
; 접수증 렌더링 해상도 (높을수록 선명, 기본 300)
render_dpi = 300

[api]
; 테넌트 이름 (store.dpl.shop의 스토어 식별자)
tenant =
; API 키 (인증 완료 시 자동 기록, 수동 편집 불필요)
api_key =
; 서버 주소
base_url = https://store.dpl.shop
; 풀링 간격 (초, 유휴 시 자동 백오프)
poll_interval = 5
```

## 의존성 (requirements.txt)

```
requests
Pillow
pywin32
pyinstaller
```

> poppler, watchdog, pdf2image 불필요.

## 빌드

```bat
@echo off
pyinstaller --onefile --name label-printer-agent main.py
echo 빌드 완료: dist\label-printer-agent.exe
pause
```

## 실행

```bash
# 개발
python main.py

# exe
label-printer-agent.exe
```

최초 실행 시:
1. config.ini의 `[api] tenant`가 비어있으면 → 설정 안내 출력 후 종료
2. `api_key`가 비어있으면 → Device Auth 자동 시작 → 브라우저 오픈 → 관리자 승인 대기
3. 승인 완료 후 자동으로 풀링 시작

## 구현 순서

### Step 1: 기반 설정
- [ ] `config.py` — config.ini 로드, `save_api_key()` 구현
- [ ] `config.ini` — `[api]` 섹션 템플릿
- [ ] `printer.py` — watcher/printer.py 복사 (공용)
- [ ] `requirements.txt`

### Step 2: 인증
- [ ] `auth.py` — Device Auth 플로우 (POST request → URL 표시 → 브라우저 오픈 → poll)
- [ ] 에러 처리 (404, 429, 410, 네트워크 오류)

### Step 3: API 클라이언트
- [ ] `api_client.py` — PrinterApiClient (get_pending_receipts, mark_printed, mark_failed)
- [ ] 커스텀 예외 (UpgradeRequiredError, AuthExpiredError)
- [ ] X-Client-Version 헤더

### Step 4: 접수증 이미지 생성
- [ ] `receipt_builder.py` — JSON → Pillow Image
- [ ] 접수증 레이아웃 (브랜드명, 주문정보, 상품목록, 금액, 결제정보)
- [ ] receiptWidthMm에 따른 폭 계산 (58/72/80mm)
- [ ] dualCopy: 매장용/고객용 copyLabel 분기
- [ ] 한글 폰트 로딩 (malgun.ttf → gulim.ttc 폴백)
- [ ] 금액 포맷 (1,000원)

### Step 5: 풀링 루프 + 통합
- [ ] `main.py` — 인증 확인 → 클라이언트 생성 → 풀링 루프
- [ ] process_receipt: 이미지 생성 → 출력 → printed/failed 보고
- [ ] adaptive 백오프 (5초→30초)
- [ ] 예외별 분기 (AuthExpired → 키 삭제, Upgrade → 종료, 네트워크 → 30초 대기)

### Step 6: 빌드 & 테스트
- [ ] `build.bat` — PyInstaller 빌드 스크립트
- [ ] exe 실행 테스트 (인증 → 풀링 → 출력)
- [ ] GitHub Actions workflow 추가 (태그 push → exe 빌드 → Release 업로드)

## API 응답 포맷

### GET /api/printer/receipts

```json
{
  "receipts": [ ... ],
  "pollInterval": 5        // (선택) 다음 풀링까지 대기 시간(초)
}
```

- `pollInterval`이 있으면 클라이언트는 해당 값을 다음 대기 시간으로 사용
- `pollInterval`이 없으면 클라이언트의 adaptive 백오프 로직 적용
- 서버에서 `pollInterval: 5`를 항상 내려주면 백오프 없이 고정 5초 동작

## API 엔드포인트 요약

| 메서드 | 엔드포인트 | 용도 | 인증 |
|--------|-----------|------|------|
| POST | `/api/printer/auth/request` | 인증 요청 생성 | 없음 |
| POST | `/api/printer/auth/poll` | 승인 여부 폴링 | 없음 |
| GET | `/api/printer/receipts?status=pending` | 미출력 접수증 조회 | API Key |
| POST | `/api/printer/receipts/{id}/printed` | 출력 완료 확인 | API Key |
| POST | `/api/printer/receipts/{id}/failed` | 출력 실패 보고 | API Key |

## 에러 코드 처리

| HTTP 상태 | 의미 | 클라이언트 동작 |
|-----------|------|----------------|
| 200 | 성공 | 정상 처리 |
| 202 | 인증 대기중 | 폴링 계속 |
| 401 | API 키 무효/해제 | api_key 삭제, 재인증 안내 후 종료 |
| 404 | 테넌트 없음 | config.ini 확인 안내 후 종료 |
| 410 | 인증 만료 | 재실행 안내 |
| 426 | 버전 업데이트 필요 | 다운로드 URL 안내 후 종료 |
| 429 | 요청 제한 | 잠시 후 재시도 안내 |
