import ctypes
import logging
import queue
import sys
import threading

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

import customtkinter as ctk

import config
from auth import authenticate
from api_client import PrinterApiClient, AuthExpiredError, UpgradeRequiredError
from receipt_builder import build_receipt_images
from printer import print_image

logger = logging.getLogger(__name__)

# 파스텔 그레이톤 컬러칩
_BG = "#2C2C2E"
_FRAME_BG = "#3A3A3C"
_TEXT = "#E0DDD9"
_TEXT_MUTED = "#8E8A85"
_GREEN = "#8BC5A3"
_CORAL = "#D4897A"
_BLUE = "#7A9EB8"
_GRAY = "#5A5856"
_LOG_BG = "#333335"
_LOG_TEXT = "#D0CCC8"
_FONT = "Malgun Gothic"
_LOG_FONT = "Malgun Gothic"


class QueueHandler(logging.Handler):
    """로그를 큐로 전달하여 GUI에서 소비."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


def _backoff_interval(empty_count: int) -> float:
    if empty_count < 3:
        return config.POLL_INTERVAL
    if empty_count < 6:
        return 10
    if empty_count < 10:
        return 20
    return 30


def process_receipt(client: PrinterApiClient, receipt: dict):
    receipt_id = receipt["id"]
    try:
        images = build_receipt_images(receipt, config.PRINTER_DPI)
        for img in images:
            print_image(img)
        client.mark_printed(receipt_id)
        logger.info("출력 완료: %s", receipt.get("orderNumber", receipt_id))
    except Exception as e:
        logger.exception("출력 실패: %s", receipt.get("orderNumber", receipt_id))
        try:
            client.mark_failed(receipt_id, str(e))
        except Exception:
            logger.exception("실패 보고 오류")


class AgentApp(ctk.CTk):
    MAX_LOG_LINES = 1000

    def __init__(self):
        super().__init__()
        self.title("DPS 라벨 프린터 - Agent")
        self.geometry("620x520")
        self.minsize(500, 400)
        self.configure(fg_color=_BG)

        ctk.set_appearance_mode("dark")

        self._log_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._polling_thread = None
        self._running = False

        self._setup_logging()
        self._build_ui()
        self._poll_log_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # 자동 시작
        self.after(200, self._start)

    def _setup_logging(self):
        handler = QueueHandler(self._log_queue)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- 상태 ---
        status_frame = ctk.CTkFrame(self, fg_color=_FRAME_BG, corner_radius=8)
        status_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        status_frame.grid_columnconfigure(1, weight=1)

        self._status_dot = ctk.CTkLabel(
            status_frame, text="●", font=(_FONT, 16), text_color=_GRAY,
        )
        self._status_dot.grid(row=0, column=0, padx=(12, 4), pady=8)

        self._status_label = ctk.CTkLabel(
            status_frame, text="중지됨",
            font=(_FONT, 14, "bold"), text_color=_TEXT,
        )
        self._status_label.grid(row=0, column=1, sticky="w")

        # --- 설정 ---
        info_frame = ctk.CTkFrame(self, fg_color=_FRAME_BG, corner_radius=8)
        info_frame.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        info_frame.grid_columnconfigure(1, weight=1)

        api_key_status = "인증 완료" if config.API_KEY else "미인증"
        settings = [
            ("프린터", config.PRINTER_NAME),
            ("서버", config.BASE_URL),
            ("인증", api_key_status),
            ("풀링 간격", f"{config.POLL_INTERVAL}초"),
        ]
        row_idx = 0
        for label, value in settings:
            ctk.CTkLabel(
                info_frame, text=label,
                font=(_FONT, 12), text_color=_TEXT_MUTED,
            ).grid(row=row_idx, column=0, padx=(12, 8), pady=2, sticky="w")
            lbl = ctk.CTkLabel(
                info_frame, text=str(value), anchor="w",
                font=(_FONT, 12), text_color=_TEXT,
            )
            lbl.grid(row=row_idx, column=1, padx=(0, 12), pady=2, sticky="w")
            if label == "인증":
                self._auth_label = lbl
            row_idx += 1

        # 테넌트 입력 필드
        ctk.CTkLabel(
            info_frame, text="테넌트",
            font=(_FONT, 12), text_color=_TEXT_MUTED,
        ).grid(row=row_idx, column=0, padx=(12, 8), pady=2, sticky="w")

        tenant_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        tenant_row.grid(row=row_idx, column=1, padx=(0, 12), pady=2, sticky="ew")
        tenant_row.grid_columnconfigure(0, weight=1)

        self._tenant_entry = ctk.CTkEntry(
            tenant_row, font=(_FONT, 12),
            fg_color=_LOG_BG, text_color=_TEXT, border_color=_GRAY,
            height=28, corner_radius=4,
        )
        self._tenant_entry.grid(row=0, column=0, sticky="ew")
        if config.API_TENANT:
            self._tenant_entry.insert(0, config.API_TENANT)

        self._tenant_save_btn = ctk.CTkButton(
            tenant_row, text="저장", width=48,
            font=(_FONT, 11), fg_color=_BLUE,
            hover_color="#6B8EA8", corner_radius=4, height=28,
            command=self._save_tenant,
        )
        self._tenant_save_btn.grid(row=0, column=1, padx=(4, 0))

        # --- 로그 ---
        log_label = ctk.CTkLabel(
            self, text="로그", font=(_FONT, 12),
            text_color=_TEXT_MUTED, anchor="w",
        )
        log_label.grid(row=2, column=0, padx=14, pady=(6, 0), sticky="nw")

        self._log_text = ctk.CTkTextbox(
            self, state="disabled",
            font=(_LOG_FONT, 11),
            fg_color=_LOG_BG, text_color=_LOG_TEXT,
            corner_radius=8,
        )
        self._log_text.grid(row=2, column=0, padx=12, pady=(24, 6), sticky="nsew")

        # --- 버튼 ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=12, pady=(6, 12), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self._start_btn = ctk.CTkButton(
            btn_frame, text="시작", command=self._start,
            font=(_FONT, 13), fg_color=_BLUE,
            hover_color="#6B8EA8", corner_radius=8,
        )
        self._start_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._stop_btn = ctk.CTkButton(
            btn_frame, text="중지", command=self._stop,
            font=(_FONT, 13), fg_color=_GRAY,
            hover_color="#6B6360", corner_radius=8, state="disabled",
        )
        self._stop_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _update_status(self, text=None, running=None):
        if running is not None:
            self._running = running
        if self._running:
            self._status_dot.configure(text_color=_GREEN)
            self._status_label.configure(text=text or "실행 중")
            self._start_btn.configure(state="disabled", fg_color=_GRAY)
            self._stop_btn.configure(state="normal", fg_color=_CORAL, hover_color="#C47A6B")
            self._tenant_entry.configure(state="disabled")
            self._tenant_save_btn.configure(state="disabled", fg_color=_GRAY)
        else:
            self._status_dot.configure(text_color=_GRAY)
            self._status_label.configure(text=text or "중지됨")
            self._start_btn.configure(state="normal", fg_color=_BLUE)
            self._stop_btn.configure(state="disabled", fg_color=_GRAY)
            self._tenant_entry.configure(state="normal")
            self._tenant_save_btn.configure(state="normal", fg_color=_BLUE)

    def _start(self):
        if self._running:
            return

        logger.info("=== 라벨 프린터 에이전트 ===")
        logger.info("프린터: %s", config.PRINTER_NAME)
        logger.info("서버: %s", config.BASE_URL)

        if not config.API_KEY:
            if not config.API_TENANT:
                logger.error("config.ini의 [api] tenant를 설정해주세요.")
                return
            self._update_status(text="인증 중...", running=True)
            threading.Thread(target=self._auth_and_start, daemon=True).start()
            return

        self._start_polling()

    def _auth_and_start(self):
        try:
            api_key = authenticate(config.API_TENANT, config.BASE_URL)
            config.save_api_key(api_key)
            self.after(0, lambda: self._auth_label.configure(text="인증 완료"))
            self.after(0, self._start_polling)
        except SystemExit:
            self.after(0, lambda: self._update_status(running=False))
        except Exception:
            logger.exception("인증 중 오류 발생")
            self.after(0, lambda: self._update_status(running=False))

    def _start_polling(self):
        self._stop_event.clear()
        self._polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._polling_thread.start()
        self._update_status(running=True)

    def _polling_loop(self):
        import requests
        client = PrinterApiClient(config.BASE_URL, config.API_KEY)
        logger.info("풀링 시작 (간격: %d초)", config.POLL_INTERVAL)
        empty_count = 0

        while not self._stop_event.is_set():
            try:
                receipts = client.get_pending_receipts()
                if not receipts:
                    empty_count += 1
                    interval = _backoff_interval(empty_count)
                    if empty_count <= 1:
                        logger.info("대기 중... (새 접수증 없음)")
                    elif empty_count % 10 == 0:
                        logger.info("대기 중... (%.0f초 간격)", interval)
                    self._stop_event.wait(interval)
                    continue

                empty_count = 0
                for receipt in receipts:
                    if self._stop_event.is_set():
                        break
                    process_receipt(client, receipt)
                self._stop_event.wait(config.POLL_INTERVAL)

            except AuthExpiredError:
                logger.error("API 키가 만료되었습니다. 재인증이 필요합니다.")
                config.save_api_key("")
                self.after(0, lambda: self._auth_label.configure(text="미인증"))
                break

            except UpgradeRequiredError as e:
                logger.error("클라이언트 업데이트가 필요합니다: %s", e)
                break

            except requests.ConnectionError:
                logger.warning("네트워크 연결 실패. 30초 후 재시도...")
                self._stop_event.wait(30)

            except Exception:
                logger.exception("풀링 중 예외 발생. 10초 후 재시도...")
                self._stop_event.wait(10)

        self.after(0, lambda: self._update_status(running=False))

    def _save_tenant(self):
        tenant = self._tenant_entry.get().strip()
        if not tenant:
            logger.warning("테넌트를 입력해주세요.")
            return
        config.save_tenant(tenant)
        logger.info("테넌트 저장됨: %s", tenant)
        # 실행 중이 아니면 자동 시작
        if not self._running:
            self._start()

    def _stop(self):
        if not self._running:
            return
        self._stop_event.set()
        logger.info("중지 요청...")

    def _poll_log_queue(self):
        has_new = False
        while not self._log_queue.empty():
            try:
                msg = self._log_queue.get_nowait()
                self._log_text.configure(state="normal")
                self._log_text.insert("end", msg + "\n")
                self._log_text.configure(state="disabled")
                has_new = True
            except queue.Empty:
                break

        if has_new:
            self._log_text.see("end")
            self._trim_log()

        self.after(100, self._poll_log_queue)

    def _trim_log(self):
        content = self._log_text.get("1.0", "end")
        lines = content.split("\n")
        if len(lines) > self.MAX_LOG_LINES:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", f"{len(lines) - self.MAX_LOG_LINES}.0")
            self._log_text.configure(state="disabled")

    def _on_closing(self):
        self._stop_event.set()
        self.destroy()
