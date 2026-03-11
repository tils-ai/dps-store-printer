import requests

VERSION = "1.0.0"


class UpgradeRequiredError(Exception):
    """서버가 클라이언트 업데이트를 요구 (426)."""
    pass


class AuthExpiredError(Exception):
    """API 키가 만료/해제됨 (401)."""
    pass


class PrinterApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers["X-Client-Version"] = VERSION
        self.base_url = base_url

    def get_pending_receipts(self, limit: int = 10) -> tuple[list[dict], int | None]:
        """미출력 접수증 조회. 서버가 PENDING→PRINTING으로 선점.
        Returns: (receipts, pollInterval)
          - pollInterval: 서버 지정 간격(초). 없으면 None → 클라이언트 백오프 사용.
        """
        resp = self.session.get(
            f"{self.base_url}/api/printer/receipts",
            params={"status": "pending", "limit": limit},
            timeout=15,
        )
        if resp.status_code == 426:
            raise UpgradeRequiredError(resp.json())
        if resp.status_code == 401:
            raise AuthExpiredError("API 키가 만료되었습니다.")
        resp.raise_for_status()
        data = resp.json()
        return data["receipts"], data.get("pollInterval")

    def mark_printed(self, receipt_id: str):
        """출력 완료 보고."""
        resp = self.session.post(
            f"{self.base_url}/api/printer/receipts/{receipt_id}/printed",
            timeout=10,
        )
        resp.raise_for_status()

    def mark_failed(self, receipt_id: str, reason: str = ""):
        """출력 실패 보고."""
        resp = self.session.post(
            f"{self.base_url}/api/printer/receipts/{receipt_id}/failed",
            json={"reason": reason} if reason else None,
            timeout=10,
        )
        resp.raise_for_status()
