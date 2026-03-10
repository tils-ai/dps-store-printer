# 라벨 프린터 자동 출력 프로그램

> 작성일: 2026-03-10

## 개요

특정 폴더를 감시하여 PDF 또는 ZIP 파일이 저장되면 자동으로 SLK TS200 라벨 프린터에 출력하는 Windows 프로그램.

## 환경

- **OS**: Windows
- **언어**: Python 3.11+
- **프린터**: SLK TS200 (감열 라벨 프린터, USB 연결, 드라이버 설치 완료)
- **라벨 규격**: 폭 72mm, 높이 가변 (PDF 페이지 비율에 따라 자동 계산)

## 핵심 흐름

```
감시 폴더에 파일 생성
  ├─ .zip → 압축 해제 → 내부 .pdf 추출
  └─ .pdf → 바로 처리
      ↓
  PDF 페이지별 이미지 변환
      ↓
  72mm 폭 기준 리사이즈 (높이는 비율 유지)
      ↓
  Windows 프린터 큐로 전송 (프린터명 지정)
      ↓
  출력 완료된 파일은 완료 폴더로 이동
```

## 요구사항

### 1. 폴더 감시

- `watchdog` 라이브러리 사용
- 감시 대상: 지정된 폴더에 `.pdf`, `.zip` 파일 생성 이벤트
- 파일 쓰기 완료 대기 (파일 크기 안정화 확인 후 처리)

### 2. ZIP 처리

- `zipfile` (내장) 사용
- ZIP 내부의 `.pdf` 파일만 추출
- 임시 폴더에 해제 후 처리, 처리 완료 시 임시 파일 삭제

### 3. PDF → 이미지 변환

- `pdf2image` + poppler 사용
- PDF의 각 페이지를 개별 이미지로 변환
- 멀티 페이지 PDF는 페이지 순서대로 모두 출력

### 4. 이미지 리사이즈

- `Pillow` 사용
- 폭 72mm 기준 (프린터 DPI에 맞게 픽셀 계산)
- 높이는 원본 비율 유지 (가변)
- 프린터 DPI: TS200 스펙 확인 필요 (일반적으로 203DPI → 72mm ≈ 576px)

### 5. 프린터 출력

- `win32print` + `win32ui` 사용 (pywin32)
- Windows에 설치된 프린터 이름으로 지정하여 출력
- 드라이버 경유 출력 (ESC/POS 직접 제어 아님)
- 페이지별로 순차 출력

### 6. 파일 관리

- 출력 완료된 원본 파일(.pdf/.zip)은 `done/` 폴더로 이동
- 출력 실패 시 `error/` 폴더로 이동 + 로그 기록

## 디렉토리 구조

```
label-printer-watcher/
├── main.py              # 진입점 (폴더 감시 시작)
├── config.py            # 설정 (감시 폴더, 프린터명, DPI 등)
├── watcher.py           # 폴더 감시 (watchdog)
├── processor.py         # 파일 처리 (ZIP 해제, PDF 변환, 출력)
├── printer.py           # 프린터 출력 (win32print)
├── requirements.txt     # 의존성
└── README.md            # 사용법
```

## 설정 (config.py)

```python
WATCH_DIR = "C:/LabelPrint/watch"     # 감시 폴더
DONE_DIR = "C:/LabelPrint/done"       # 완료 폴더
ERROR_DIR = "C:/LabelPrint/error"     # 실패 폴더
PRINTER_NAME = "SLK TS200"            # Windows 프린터 이름 (정확히 일치)
LABEL_WIDTH_MM = 72                    # 라벨 폭
PRINTER_DPI = 203                      # 프린터 DPI (TS200 스펙 확인)
```

## 의존성

```
watchdog
pdf2image
Pillow
pywin32
```

추가로 **poppler** Windows 바이너리 설치 필요 (`pdf2image`가 내부적으로 사용).

## 실행

```bash
python main.py
```

- 콘솔에서 실행, Ctrl+C로 종료
- 추후 필요 시 Windows 서비스로 등록 가능

## 주의사항

- 프린터 이름은 Windows 설정 > 프린터에서 정확한 이름 확인 필요
- poppler 설치 경로를 `pdf2image`에 전달하거나 PATH에 추가
- 파일 쓰기 중 처리 방지: 파일 크기를 1초 간격으로 2회 비교하여 동일하면 처리 시작
- PDF 원본은 80mm 폭 기준으로 생성됨 (DPS Store 접수증) → 72mm로 리사이즈
