"""Agent worker — dps-store API 풀링 → 접수증 출력.

기존 agent/gui.py의 process_receipt + _polling_loop를 단독 모듈로 추출.
GUI는 watcher/gui/app.py에서 이 워커를 시작/정지한다.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import requests

import config
from api_client import AuthExpiredError, PrinterApiClient, UpgradeRequiredError
from auth import authenticate
from printer import print_image
from receipt_builder import build_receipt_images

logger = logging.getLogger(__name__)


def _backoff_interval(empty_count: int) -> float:
    if empty_count < 3:
        return config.POLL_INTERVAL
    if empty_count < 6:
        return 10
    if empty_count < 10:
        return 20
    return 30


def _process_receipt(
    client: PrinterApiClient,
    receipt: dict,
    *,
    on_done: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    receipt_id = receipt["id"]
    name = receipt.get("orderNumber", receipt_id)
    try:
        images = build_receipt_images(receipt, config.PRINTER_DPI)
        for img in images:
            print_image(img)
        client.mark_printed(receipt_id)
        logger.info("출력 완료: %s", name)
        if on_done:
            on_done(name)
    except Exception as e:
        logger.exception("출력 실패: %s", name)
        try:
            client.mark_failed(receipt_id, str(e))
        except Exception:
            logger.exception("실패 보고 오류")
        if on_error:
            on_error(name)


class AgentWorker:
    """Device Auth → 풀링 루프 → 접수증 처리."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # 표준 콜백 셋 (g/l/m 통일) — 모두 Optional, 미지정 시 무시
        self.on_started: Optional[Callable[[], None]] = None
        self.on_stopped: Optional[Callable[[], None]] = None
        self.on_downloaded: Optional[Callable[[str], None]] = None
        self.on_done: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_auth_expired: Optional[Callable[[], None]] = None

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        if not config.API_KEY:
            if not config.API_TENANT:
                logger.error("config.ini의 [api] tenant를 설정해주세요.")
                return
            logger.info("인증 시작 — tenant: %s", config.API_TENANT)
            threading.Thread(target=self._auth_and_start, daemon=True).start()
            return
        self._start_polling()

    def stop(self) -> None:
        if not self._running and self._thread is None:
            return
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._running = False
        _fire(self.on_stopped)

    def _auth_and_start(self) -> None:
        try:
            api_key = authenticate(config.API_TENANT, config.BASE_URL)
            config.save_api_key(api_key)
            self._start_polling()
        except SystemExit:
            return
        except Exception:
            logger.exception("인증 오류")

    def _start_polling(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._thread.start()
        self._running = True
        _fire(self.on_started)

    def _polling_loop(self) -> None:
        client = PrinterApiClient(config.BASE_URL, config.API_KEY)
        logger.info("풀링 시작 (간격: %d초)", config.POLL_INTERVAL)
        empty_count = 0
        while not self._stop_event.is_set():
            try:
                receipts, server_interval = client.get_pending_receipts()
                if not receipts:
                    empty_count += 1
                    interval = server_interval or _backoff_interval(empty_count)
                    if empty_count <= 1:
                        logger.info("대기 중...")
                    elif empty_count % 10 == 0:
                        logger.info("대기 중... (%.0f초 간격)", interval)
                    self._stop_event.wait(interval)
                    continue
                empty_count = 0
                for receipt in receipts:
                    if self._stop_event.is_set():
                        break
                    # l-module은 즉시 출력 — on_downloaded와 on_done 시점이 사실상 동일
                    receipt_name = receipt.get("orderNumber", receipt.get("id", ""))
                    _fire(self.on_downloaded, receipt_name)
                    _process_receipt(client, receipt, on_done=self.on_done, on_error=self.on_error)
                interval = server_interval or config.POLL_INTERVAL
                self._stop_event.wait(interval)
            except AuthExpiredError:
                logger.error("API 키 만료 — 재인증 필요")
                config.save_api_key("")
                _fire(self.on_auth_expired)
                break
            except UpgradeRequiredError as e:
                logger.error("클라이언트 업데이트 필요: %s", e)
                break
            except requests.ConnectionError:
                logger.warning("네트워크 연결 실패 — 30초 후 재시도")
                self._stop_event.wait(30)
            except Exception:
                logger.exception("풀링 예외 — 10초 후 재시도")
                self._stop_event.wait(10)
        self._running = False


def _fire(cb, *args):
    """콜백을 안전하게 호출 — 미지정이거나 예외면 무시."""
    if cb is None:
        return
    try:
        cb(*args)
    except Exception:
        logger.exception("콜백 예외 — 무시하고 계속")
