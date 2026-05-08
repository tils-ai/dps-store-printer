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

_DEFAULT_INI = """\
[printer]
; Windows 설정 > 프린터에서 정확한 이름 확인
name = SLK TS200
dpi = 203
; 렌더링 해상도 (높을수록 선명, 기본 300)
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

[gui]
; system | light | dark
appearance = system
"""

# config.ini가 없으면 기본값으로 생성
if not os.path.exists(INI_PATH):
    with open(INI_PATH, "w", encoding="utf-8") as f:
        f.write(_DEFAULT_INI)

_ini = configparser.ConfigParser()
_ini.read(INI_PATH, encoding="utf-8")

PRINTER_NAME = _ini.get("printer", "name", fallback="SLK TS200")
PRINTER_DPI = _ini.getint("printer", "dpi", fallback=203)
RENDER_DPI = _ini.getint("printer", "render_dpi", fallback=300)

API_TENANT = _ini.get("api", "tenant", fallback="")
API_KEY = _ini.get("api", "api_key", fallback="")
BASE_URL = _ini.get("api", "base_url", fallback="https://store.dpl.shop")
POLL_INTERVAL = _ini.getint("api", "poll_interval", fallback=5)


def get_appearance() -> str:
    p = configparser.ConfigParser()
    p.read(INI_PATH, encoding="utf-8")
    value = p.get("gui", "appearance", fallback="system").strip().lower()
    return value if value in {"system", "light", "dark"} else "system"


def set_appearance(value: str) -> None:
    value = (value or "system").strip().lower()
    if value not in {"system", "light", "dark"}:
        value = "system"
    p = configparser.ConfigParser()
    p.read(INI_PATH, encoding="utf-8")
    if not p.has_section("gui"):
        p.add_section("gui")
    p.set("gui", "appearance", value)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        p.write(f)


def _ensure_api_section():
    if not _ini.has_section("api"):
        _ini.add_section("api")


def save_api_key(api_key: str):
    """인증 성공 후 API 키를 config.ini [api] 섹션에 기록."""
    global API_KEY
    API_KEY = api_key
    _ensure_api_section()
    _ini.set("api", "api_key", api_key)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)


def save_tenant(tenant: str):
    """테넌트를 config.ini [api] 섹션에 기록."""
    global API_TENANT
    API_TENANT = tenant
    _ensure_api_section()
    _ini.set("api", "tenant", tenant)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)
