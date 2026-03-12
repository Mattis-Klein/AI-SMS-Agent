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

    def get_overview(self) -> dict:
        return self._request("GET", "/control-board/overview", include_auth=True)

    def get_activity(self, limit: int = 100) -> dict:
        return self._request("GET", f"/control-board/activity?limit={int(limit)}", include_auth=True)

    def get_assistants(self) -> dict:
        return self._request("GET", "/control-board/assistants", include_auth=True)

    def get_routing(self) -> dict:
        return self._request("GET", "/control-board/routing", include_auth=True)

    def approve_routing_member(self, phone_number: str, activate_now: bool = False) -> dict:
        return self._request(
            "POST",
            "/control-board/routing/approve",
            include_auth=True,
            body={"phone_number": phone_number, "activate_now": bool(activate_now)},
        )

    def deactivate_routing_member(self, phone_number: str) -> dict:
        return self._request(
            "POST",
            "/control-board/routing/deactivate",
            include_auth=True,
            body={"phone_number": phone_number},
        )

    def get_email_config(self) -> dict:
        return self._request("GET", "/control-board/email-config", include_auth=True)

    def save_email_config(
        self,
        *,
        provider: str,
        email_address: str,
        password: str,
        imap_host: str,
        imap_port: int,
        use_ssl: bool,
        mailbox: str,
    ) -> dict:
        return self._request(
            "POST",
            "/control-board/email-config/save",
            include_auth=True,
            body={
                "provider": provider,
                "email_address": email_address,
                "password": password,
                "imap_host": imap_host,
                "imap_port": int(imap_port),
                "use_ssl": bool(use_ssl),
                "mailbox": mailbox,
            },
        )

    def test_email_connection(self) -> dict:
        return self._request("POST", "/control-board/email-config/test", include_auth=True, body={})

    def get_files_policy(self) -> dict:
        return self._request("GET", "/control-board/files-policy", include_auth=True)

    def save_files_policy(self, allowed_directories: list[str]) -> dict:
        return self._request(
            "POST",
            "/control-board/files-policy/save",
            include_auth=True,
            body={"allowed_directories": allowed_directories},
        )

    def test_policy_path(self, path: str) -> dict:
        return self._request(
            "POST",
            "/control-board/files-policy/test-path",
            include_auth=True,
            body={"path": path},
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
