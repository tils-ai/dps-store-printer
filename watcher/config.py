import configparser
import os
import sys


def _base_dir():
    """exe 파일이 있는 폴더 (spec §11.5)."""
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
; 실물 프린터 없이 preview/ 폴더에 PNG로 저장 (테스트용)
; 환경변수 LABEL_PRINTER_DRYRUN=1 로도 일시적으로 활성화 가능
dryrun = false

[api]
; dps-store API 풀링 (v3.0에서 watcher+agent 통합)
tenant =
api_key =
base_url = https://store.dpl.shop
poll_interval = 5

[paths]
; spec §11.5 통일 키 (비워두면 자동)
incoming =
processing =
done =
originals =
error =

[log]
file =
level = INFO

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

def _path_fallback(paths_key: str, legacy_key: str, default_sub: str) -> str:
    val = _ini.get("paths", paths_key, fallback="").strip()
    if not val:
        val = _ini.get("folder", legacy_key, fallback="").strip()
    return val or os.path.join(BASE_DIR, default_sub)


INCOMING_DIR = _path_fallback("incoming", "watch", "incoming")
PROCESSING_DIR = _ini.get("paths", "processing", fallback="").strip() or os.path.join(BASE_DIR, "processing")
DONE_DIR = _path_fallback("done", "done", "done")
ORIGINALS_DIR = _ini.get("paths", "originals", fallback="").strip() or os.path.join(DONE_DIR, "originals")
ERROR_DIR = _path_fallback("error", "error", "error")
LOG_FILE = _ini.get("log", "file", fallback="").strip() or os.path.join(BASE_DIR, "logs", "watcher.log")
LOG_LEVEL = _ini.get("log", "level", fallback="INFO").strip().upper()
PRINTER_NAME = _ini.get("printer", "name", fallback="SLK TS200")

for _d in (INCOMING_DIR, PROCESSING_DIR, DONE_DIR, ORIGINALS_DIR, ERROR_DIR, os.path.dirname(LOG_FILE)):
    if _d:
        os.makedirs(_d, exist_ok=True)


# --- API 풀링 (v3.0 통합) ---
API_TENANT = _ini.get("api", "tenant", fallback="")
API_KEY = _ini.get("api", "api_key", fallback="")
BASE_URL = _ini.get("api", "base_url", fallback="https://store.dpl.shop")
POLL_INTERVAL = _ini.getint("api", "poll_interval", fallback=5)


def _ensure_section(name: str) -> None:
    if not _ini.has_section(name):
        _ini.add_section(name)


def save_api_key(api_key: str) -> None:
    """인증 성공 후 API 키를 config.ini [api] 섹션에 기록."""
    global API_KEY
    API_KEY = api_key
    _ensure_section("api")
    _ini.set("api", "api_key", api_key)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)


def save_tenant(tenant: str) -> None:
    """테넌트를 config.ini [api] 섹션에 기록."""
    global API_TENANT
    API_TENANT = tenant
    _ensure_section("api")
    _ini.set("api", "tenant", tenant)
    with open(INI_PATH, "w", encoding="utf-8") as f:
        _ini.write(f)


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
LABEL_WIDTH_MM = 72
PRINTER_DPI = _ini.getint("printer", "dpi", fallback=203)
RENDER_DPI = _ini.getint("printer", "render_dpi", fallback=300)
LABEL_WIDTH_PX = int(LABEL_WIDTH_MM / 25.4 * PRINTER_DPI)  # ~576px

# DRYRUN: 실물 프린터 없이 PNG로 저장 (테스트/지사 출장 시 사용)
# 환경변수가 우선, 없으면 config.ini 값
PRINTER_DRYRUN = (
    os.environ.get("LABEL_PRINTER_DRYRUN", "").strip().lower() in {"1", "true", "yes", "on"}
    or _ini.getboolean("printer", "dryrun", fallback=False)
)
PREVIEW_DIR = os.path.join(BASE_DIR, "preview")

# poppler 경로 (pdf2image에서 사용)
# 우선순위: config.ini > exe 번들 > PATH
def _poppler_path():
    ini_path = _ini.get("poppler", "path", fallback="")
    if ini_path:
        return ini_path
    # PyInstaller 번들 내 poppler 확인
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, "poppler")
        if os.path.isdir(bundled):
            return bundled
    return None

POPPLER_PATH = _poppler_path()

# 파일 쓰기 완료 대기 설정
FILE_STABLE_CHECK_INTERVAL = 1.0  # 초
FILE_STABLE_CHECK_COUNT = 2       # 비교 횟수
