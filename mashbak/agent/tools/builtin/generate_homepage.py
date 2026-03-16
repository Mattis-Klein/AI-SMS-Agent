from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ..base import Tool, ToolResult
from .path_utils import resolve_safe_path


class GenerateHomepageTool(Tool):
    def __init__(self):
        super().__init__(
            name="generate_homepage",
            description="Generate a simple colorful HTML homepage from a natural-language prompt",
            requires_args=True,
            category="creative",
            safety={"destructive": False},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str]:
        if not str(args.get("project_path") or "").strip():
            return False, "project_path is required"
        if not str(args.get("prompt") or "").strip():
            return False, "prompt is required"
        return True, ""

    def _render_html(self, prompt: str, title: str) -> str:
        body = prompt.strip().replace("<", "&lt;").replace(">", "&gt;")
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(120deg, #f6d365, #fda085); color:#1f2937; }}
    .wrap {{ max-width: 900px; margin: 60px auto; background:#fff8ee; border-radius:18px; padding:36px; box-shadow:0 20px 40px rgba(0,0,0,.15); }}
    h1 {{ margin-top:0; font-size:2.2rem; }}
    p {{ line-height:1.6; }}
    .cta {{ display:inline-block; padding:12px 18px; border-radius:10px; background:#ca3c25; color:#fff; text-decoration:none; }}
  </style>
</head>
<body>
  <main class=\"wrap\">
    <h1>{title}</h1>
    <p>{body}</p>
    <p><a class=\"cta\" href=\"#\">Order Now</a></p>
  </main>
</body>
</html>
"""

    async def execute(self, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ToolResult:
        workspace = context.get("workspace") if context else None
        allowed_dirs = context.get("allowed_directories", []) if context else []
        if not workspace:
            return ToolResult(success=False, output="", error="Workspace not configured", tool_name=self.name)

        project_path = str(args.get("project_path") or "").strip()
        ok, reason, folder = resolve_safe_path(project_path, Path(workspace), allowed_dirs)
        if not ok or folder is None:
            return ToolResult(success=False, output="", error=reason, error_type="denied_action", tool_name=self.name, arguments=args)

        folder.mkdir(parents=True, exist_ok=True)
        title = str(args.get("title") or "Generated Homepage").strip() or "Generated Homepage"
        html = self._render_html(str(args.get("prompt") or ""), title)
        target = folder / "index.html"
        target.write_text(html, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Homepage generated at {target}",
            tool_name=self.name,
            arguments=args,
            data={"project_path": str(folder), "entry_file": str(target), "created_files": [str(target)]},
        )
