import logging
import queue
import threading

import customtkinter as ctk

import config

logger = logging.getLogger(__name__)


class QueueHandler(logging.Handler):
    """로그를 큐로 전달하여 GUI에서 소비."""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))


class WatcherApp(ctk.CTk):
    MAX_LOG_LINES = 1000

    def __init__(self):
        super().__init__()
        self.title("DPS 라벨 프린터 - Watcher")
        self.geometry("620x520")
        self.minsize(500, 400)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._log_queue = queue.Queue()
        self._observer = None
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
        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        status_frame.grid_columnconfigure(1, weight=1)

        self._status_dot = ctk.CTkLabel(status_frame, text="●", font=("", 16))
        self._status_dot.grid(row=0, column=0, padx=(12, 4), pady=8)

        self._status_label = ctk.CTkLabel(status_frame, text="중지됨", font=("", 14, "bold"))
        self._status_label.grid(row=0, column=1, sticky="w")

        # --- 설정 ---
        info_frame = ctk.CTkFrame(self)
        info_frame.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        info_frame.grid_columnconfigure(1, weight=1)

        settings = [
            ("프린터", config.PRINTER_NAME),
            ("감시 폴더", config.WATCH_DIR),
            ("완료 폴더", config.DONE_DIR),
            ("DPI", f"{config.PRINTER_DPI} (렌더링 {config.RENDER_DPI})"),
        ]
        for i, (label, value) in enumerate(settings):
            ctk.CTkLabel(info_frame, text=label, text_color="gray").grid(
                row=i, column=0, padx=(12, 8), pady=2, sticky="w",
            )
            ctk.CTkLabel(info_frame, text=str(value), anchor="w").grid(
                row=i, column=1, padx=(0, 12), pady=2, sticky="w",
            )

        # --- 로그 ---
        log_label = ctk.CTkLabel(self, text="로그", font=("", 12), anchor="w")
        log_label.grid(row=2, column=0, padx=14, pady=(6, 0), sticky="nw")

        self._log_text = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 12))
        self._log_text.grid(row=2, column=0, padx=12, pady=(24, 6), sticky="nsew")

        # --- 버튼 ---
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=12, pady=(6, 12), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self._start_btn = ctk.CTkButton(btn_frame, text="시작", command=self._start)
        self._start_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._stop_btn = ctk.CTkButton(btn_frame, text="중지", command=self._stop,
                                        fg_color="gray", state="disabled")
        self._stop_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    def _update_status(self):
        if self._running:
            self._status_dot.configure(text_color="#2ecc71")
            self._status_label.configure(text="실행 중")
            self._start_btn.configure(state="disabled")
            self._stop_btn.configure(state="normal", fg_color="#e74c3c")
        else:
            self._status_dot.configure(text_color="gray")
            self._status_label.configure(text="중지됨")
            self._start_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled", fg_color="gray")

    def _start(self):
        if self._running:
            return
        from watcher import start_watching
        self._observer = start_watching()
        self._running = True
        self._update_status()
        logger.info("=== 라벨 프린터 자동 출력 프로그램 ===")
        logger.info("감시 폴더: %s", config.WATCH_DIR)
        logger.info("프린터: %s", config.PRINTER_NAME)

    def _stop(self):
        if not self._running:
            return
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        self._running = False
        self._update_status()
        logger.info("감시 중지됨")

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
        """로그가 너무 길면 오래된 줄 삭제."""
        content = self._log_text.get("1.0", "end")
        lines = content.split("\n")
        if len(lines) > self.MAX_LOG_LINES:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", f"{len(lines) - self.MAX_LOG_LINES}.0")
            self._log_text.configure(state="disabled")

    def _on_closing(self):
        self._stop()
        self.destroy()
