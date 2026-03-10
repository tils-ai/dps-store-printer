import logging
import time
import sys

import config
from watcher import start_watching

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("=== 라벨 프린터 자동 출력 프로그램 ===")
    logger.info("감시 폴더: %s", config.WATCH_DIR)
    logger.info("프린터: %s", config.PRINTER_NAME)
    logger.info("라벨 폭: %dmm (%dpx @ %dDPI)", config.LABEL_WIDTH_MM, config.LABEL_WIDTH_PX, config.PRINTER_DPI)

    observer = start_watching()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("종료 요청 수신")
    finally:
        observer.stop()
        observer.join()
        logger.info("프로그램 종료")


if __name__ == "__main__":
    main()
