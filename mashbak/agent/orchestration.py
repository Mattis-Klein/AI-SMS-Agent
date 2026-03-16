from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PlanStep:
    tool_name: str
    args: dict[str, Any]


class ActionOrchestrator:
    def __init__(self, runtime):
        self.runtime = runtime

    def build_plan(self, message: str, parsed: dict[str, Any]) -> list[PlanStep]:
        tool = parsed.get("tool")
        args = parsed.get("args") or {}
        if not tool:
            return []

        # Small multi-step project workflow for homepage generation:
        # ensure folder exists, then generate homepage.
        if tool == "generate_homepage":
            project_path = str(args.get("project_path") or "workspace/generated-site")
            return [
                PlanStep(tool_name="create_folder", args={"path": project_path}),
                PlanStep(tool_name="generate_homepage", args=args),
            ]

        return [PlanStep(tool_name=tool, args=args)]

    async def execute_plan(
        self,
        message: str,
        parsed: dict[str, Any],
        *,
        sender: str,
        source: str,
        request_id: str,
        owner_unlocked: bool | None,
    ) -> dict[str, Any]:
        steps = self.build_plan(message, parsed)
        if not steps:
            return {
                "success": False,
                "tool_name": None,
                "output": "No executable steps were produced for this request.",
                "error": "No executable steps were produced for this request.",
                "error_type": "planning_failure",
                "request_id": request_id,
                "trace": {
                    "execution_status": "failed",
                    "execution_result": "planning_failure",
                    "plan": [],
                },
            }

        task = self.runtime.task_store.create_task(
            title=f"Plan: {message[:80]}",
            source=source,
            sender=sender,
            steps=[{"tool_name": step.tool_name, "args": step.args, "status": "pending"} for step in steps],
        )

        step_results: list[dict[str, Any]] = []
        for index, step in enumerate(steps):
            rows = task.get("steps") or []
            if index < len(rows):
                rows[index]["status"] = "running"
            self.runtime.task_store.update_task(task["task_id"], steps=rows)

            result = await self.runtime.execute_tool(
                tool_name=step.tool_name,
                args=step.args,
                sender=sender,
                request_id=request_id,
                source=source,
                owner_unlocked=owner_unlocked,
            )
            step_results.append(result)

            rows = task.get("steps") or []
            if index < len(rows):
                rows[index]["status"] = "completed" if result.get("success") else "failed"
                rows[index]["result"] = {
                    "success": result.get("success"),
                    "error": result.get("error"),
                    "tool_name": result.get("tool_name"),
                }
            self.runtime.task_store.update_task(task["task_id"], steps=rows)

            if not result.get("success"):
                self.runtime.task_store.update_task(task["task_id"], status="failed", result={"step_results": step_results})
                result_trace = result.get("trace") or {}
                result_trace["plan"] = [{"tool_name": s.tool_name, "args": s.args} for s in steps]
                result_trace["step_results"] = step_results
                result_trace["task_id"] = task["task_id"]
                result["trace"] = result_trace
                return result

        final = step_results[-1]
        self.runtime.task_store.update_task(task["task_id"], status="completed", result={"step_results": step_results})
        final_trace = final.get("trace") or {}
        final_trace["plan"] = [{"tool_name": s.tool_name, "args": s.args} for s in steps]
        final_trace["step_results"] = step_results
        final_trace["task_id"] = task["task_id"]
        final["trace"] = final_trace
        return final
