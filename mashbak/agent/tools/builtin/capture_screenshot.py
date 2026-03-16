from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult

try:
    from PIL import ImageGrab
except Exception:  # pragma: no cover
    ImageGrab = None


class CaptureScreenshotTool(Tool):
    def __init__(self):
        super().__init__(
            name="capture_screenshot",
            description="Capture a screenshot and save it under workspace/outbox/screenshots",
            requires_args=False,
            category="system",
            safety={"destructive": False, "sensitive": True},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        return True, ""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        if ImageGrab is None:
            return ToolResult(success=False, output="", error="Screenshot support is unavailable (Pillow not installed)", error_type="missing_dependency", tool_name=self.name)
        workspace = context.get("workspace") if context else None
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

        dest_dir = Path(workspace) / "outbox" / "screenshots"
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = dest_dir / f"screenshot-{stamp}.png"

        image = ImageGrab.grab(all_screens=True)
        image.save(target)

        return ToolResult(success=True, output=f"Screenshot saved: {target}", tool_name=self.name, arguments=args, data={"path": str(target), "media_type": "image/png"})
