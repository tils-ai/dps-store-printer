import configparser
import os
import sys


def _base_dir():
    """exe 실행 시 exe가 있는 폴더, 스크립트 실행 시 스크립트 폴더 반환."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()
INI_PATH = os.path.join(BASE_DIR, "config.ini")

# config.ini 로드 (없으면 기본값 사용)
_ini = configparser.ConfigParser()
_ini.read(INI_PATH, encoding="utf-8")

PRINTER_NAME = _ini.get("printer", "name", fallback="SLK TS200")
PRINTER_DPI = _ini.getint("printer", "dpi", fallback=203)
RENDER_DPI = _ini.getint("printer", "render_dpi", fallback=300)

API_TENANT = _ini.get("api", "tenant", fallback="")
API_KEY = _ini.get("api", "api_key", fallback="")
BASE_URL = _ini.get("api", "base_url", fallback="https://store.dpl.shop")
POLL_INTERVAL = _ini.getint("api", "poll_interval", fallback=5)


def save_api_key(api_key: str):
    """인증 성공 후 API 키를 config.ini [api] 섹션에 기록."""
    global API_KEY
    API_KEY = api_key
    if not _ini.has_section("api"):
        _ini.add_section("api")
    _ini.set("api", "api_key", api_key)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)
