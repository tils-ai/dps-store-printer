import logging
import time
import webbrowser

import requests

logger = logging.getLogger(__name__)


def authenticate(tenant: str, base_url: str) -> str:
    """Device Auth 플로우로 API 키를 발급받는다.

    1. 인증 요청 생성
    2. 브라우저로 인증 URL 오픈
    3. 승인될 때까지 폴링
    4. API 키 반환
    """
    # 1. 인증 요청
    try:
        resp = requests.post(
            f"{base_url}/api/printer/auth/request",
            json={"tenant": tenant},
            timeout=10,
        )
    except requests.ConnectionError:
        logger.error("서버에 연결할 수 없습니다: %s", base_url)
        raise SystemExit(1)

    if resp.status_code == 404:
        logger.error("테넌트를 찾을 수 없습니다. config.ini의 [api] tenant 설정을 확인하세요.")
        raise SystemExit(1)
    if resp.status_code == 429:
        logger.error("요청이 너무 많습니다. 잠시 후 다시 시도하세요.")
        raise SystemExit(1)
    resp.raise_for_status()

    data = resp.json()
    device_code = data["deviceCode"]
    user_code = data["userCode"]
    verify_url = data["verifyUrl"]
    expires_in = data.get("expiresIn", 300)

    # 2. 브라우저 오픈
    logger.info("=" * 50)
    logger.info("  프린터 인증이 필요합니다")
    logger.info("  인증 URL: %s", verify_url)
    logger.info("  인증 코드: %s", user_code)
    logger.info("  브라우저에서 위 URL을 열고 코드를 입력하세요.")
    logger.info("  관리자가 승인하면 자동으로 시작됩니다.")
    logger.info("=" * 50)

    webbrowser.open(verify_url)

    # 3. 승인 폴링
    poll_interval = 2
    elapsed = 0

    while elapsed < expires_in:
        time.sleep(poll_interval)
        elapsed += poll_interval

        try:
            poll_resp = requests.post(
                f"{base_url}/api/printer/auth/poll",
                json={"deviceCode": device_code},
                timeout=10,
            )
        except requests.ConnectionError:
            logger.warning("네트워크 연결 실패. 재시도 중...")
            continue

        if poll_resp.status_code == 202:
            # 아직 대기 중
            continue
        if poll_resp.status_code == 410:
            logger.error("인증 시간이 만료되었습니다. 프로그램을 다시 실행하세요.")
            raise SystemExit(1)
        if poll_resp.status_code == 429:
            time.sleep(5)
            continue

        poll_resp.raise_for_status()
        poll_data = poll_resp.json()

        if poll_data.get("apiKey"):
            logger.info("인증 성공!")
            return poll_data["apiKey"]

    logger.error("인증 시간이 만료되었습니다. 프로그램을 다시 실행하세요.")
    raise SystemExit(1)
