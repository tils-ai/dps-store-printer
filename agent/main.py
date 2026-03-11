import logging
import time

import requests

import config
from auth import authenticate
from api_client import PrinterApiClient, AuthExpiredError, UpgradeRequiredError
from receipt_builder import build_receipt_images
from printer import print_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _backoff_interval(empty_count: int) -> float:
    """빈 응답 연속 횟수에 따른 풀링 간격."""
    if empty_count < 3:
        return config.POLL_INTERVAL
    if empty_count < 6:
        return 10
    if empty_count < 10:
        return 20
    return 30


def process_receipt(client: PrinterApiClient, receipt: dict):
    """접수증 이미지 생성 → 출력 → 서버에 결과 보고."""
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


def start_polling(client: PrinterApiClient):
    """서버를 풀링하며 접수증을 처리한다."""
    logger.info("풀링 시작 (간격: %d초)", config.POLL_INTERVAL)
    empty_count = 0

    while True:
        try:
            receipts = client.get_pending_receipts()

            if not receipts:
                empty_count += 1
                interval = _backoff_interval(empty_count)
                time.sleep(interval)
                continue

            empty_count = 0

            for receipt in receipts:
                process_receipt(client, receipt)

            time.sleep(config.POLL_INTERVAL)

        except AuthExpiredError:
            logger.error("API 키가 만료되었습니다. 프로그램을 다시 실행하여 재인증하세요.")
            config.save_api_key("")
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


def main():
    logger.info("=== 라벨 프린터 에이전트 ===")
    logger.info("프린터: %s", config.PRINTER_NAME)
    logger.info("서버: %s", config.BASE_URL)

    # 1. API 키 확인
    if not config.API_KEY:
        if not config.API_TENANT:
            print("config.ini의 [api] tenant를 설정해주세요.")
            input("아무 키나 누르면 종료...")
            return
        api_key = authenticate(config.API_TENANT, config.BASE_URL)
        config.save_api_key(api_key)

    # 2. API 클라이언트 생성
    client = PrinterApiClient(config.BASE_URL, config.API_KEY)

    # 3. 풀링 루프
    start_polling(client)

    input("아무 키나 누르면 종료...")


if __name__ == "__main__":
    main()
