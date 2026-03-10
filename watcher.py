import logging
import os
import time
import threading

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
from processor import process_file

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {".pdf", ".zip"}


class LabelFileHandler(FileSystemEventHandler):
    """감시 폴더에 파일이 생성되면 처리한다."""

    def on_created(self, event):
        if event.is_directory:
            return
        ext = os.path.splitext(event.src_path)[1].lower()
        if ext not in SUPPORTED_EXT:
            return
        logger.info("파일 감지: %s", event.src_path)
        # 별도 스레드에서 파일 안정화 대기 후 처리
        t = threading.Thread(target=self._wait_and_process, args=(event.src_path,), daemon=True)
        t.start()

    def _wait_and_process(self, file_path: str):
        """파일 쓰기 완료를 대기한 뒤 처리."""
        try:
            if not self._wait_for_stable(file_path):
                logger.warning("파일 안정화 실패 (삭제됨?): %s", file_path)
                return
            process_file(file_path)
        except Exception:
            logger.exception("파일 처리 중 예외: %s", file_path)

    @staticmethod
    def _wait_for_stable(file_path: str, timeout: float = 30.0) -> bool:
        """파일 크기가 안정될 때까지 대기. 삭제된 경우 False 반환."""
        interval = config.FILE_STABLE_CHECK_INTERVAL
        required = config.FILE_STABLE_CHECK_COUNT
        stable = 0
        prev_size = -1
        elapsed = 0.0

        while elapsed < timeout:
            if not os.path.exists(file_path):
                return False
            size = os.path.getsize(file_path)
            if size == prev_size and size > 0:
                stable += 1
                if stable >= required:
                    return True
            else:
                stable = 0
            prev_size = size
            time.sleep(interval)
            elapsed += interval
        return False


def start_watching():
    """감시 폴더를 관찰하고 Observer를 반환한다."""
    os.makedirs(config.WATCH_DIR, exist_ok=True)
    observer = Observer()
    observer.schedule(LabelFileHandler(), config.WATCH_DIR, recursive=False)
    observer.start()
    logger.info("폴더 감시 시작: %s", config.WATCH_DIR)
    return observer
