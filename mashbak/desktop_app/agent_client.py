"""HTTP client for local desktop app to talk to the embedded agent service."""

import json
import urllib.error
import urllib.request


class AgentClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def health(self) -> dict:
        return self._request("GET", "/health")

    def list_tools(self) -> dict:
        return self._request("GET", "/tools", include_auth=True)

    def execute_nl(self, message: str, sender: str = "local-desktop", owner_unlocked: bool | None = None) -> dict:
        return self._request(
            "POST",
            "/execute-nl",
            include_auth=True,
            include_sender=True,
            sender=sender,
            body={"message": message, "owner_unlocked": owner_unlocked},
        )

    def _request(
        self,
        method: str,
        path: str,
        include_auth: bool = False,
        include_sender: bool = False,
        sender: str = "local-desktop",
        body: dict | None = None,
    ) -> dict:
        url = f"{self.base_url}{path}"
        headers = {}
        if include_auth:
            headers["x-api-key"] = self.api_key
        if include_sender:
            headers["x-sender"] = sender
            headers["x-source"] = "desktop"

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, method=method, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=30.0) as response:
                payload = response.read().decode("utf-8", errors="replace")
                return json.loads(payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return {
                "success": False,
                "error": f"HTTP {exc.code}: {detail}",
                "tool_name": None,
                "trace": {},
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "tool_name": None,
                "trace": {},
            }
