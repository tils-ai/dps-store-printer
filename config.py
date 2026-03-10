import configparser
import os
import sys


def _base_dir():
    """exe 실행 시 exe가 있는 폴더, 스크립트 실행 시 스크립트 폴더 반환."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()

# config.ini 로드 (없으면 기본값 사용)
_ini = configparser.ConfigParser()
_ini.read(os.path.join(BASE_DIR, "config.ini"), encoding="utf-8")

WATCH_DIR = os.path.join(BASE_DIR, "watch")
DONE_DIR = os.path.join(BASE_DIR, "done")
ERROR_DIR = os.path.join(BASE_DIR, "error")
PRINTER_NAME = _ini.get("printer", "name", fallback="SLK TS200")
LABEL_WIDTH_MM = 72
PRINTER_DPI = _ini.getint("printer", "dpi", fallback=203)
LABEL_WIDTH_PX = int(LABEL_WIDTH_MM / 25.4 * PRINTER_DPI)  # ~576px

# poppler 경로 (pdf2image에서 사용)
POPPLER_PATH = _ini.get("poppler", "path", fallback=None)

# 파일 쓰기 완료 대기 설정
FILE_STABLE_CHECK_INTERVAL = 1.0  # 초
FILE_STABLE_CHECK_COUNT = 2       # 비교 횟수
