from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

if __package__:
    from .routes import create_control_board_router, create_execution_router, create_system_router
    from .runtime import create_runtime
    from .voice_handler import create_voice_router
else:
    _agent_dir = Path(__file__).resolve().parent
    _root_dir = _agent_dir.parent
    for _path in (str(_root_dir), str(_agent_dir)):
        if _path not in sys.path:
            sys.path.insert(0, _path)
    from routes import create_control_board_router, create_execution_router, create_system_router
    from runtime import create_runtime
    from voice_handler import create_voice_router


app = FastAPI(title="Mashbak", version="2.0.0")
runtime = create_runtime()

app.include_router(create_system_router(runtime))
app.include_router(create_execution_router(runtime))
app.include_router(create_control_board_router(runtime))
app.include_router(create_voice_router(runtime))


@app.on_event("startup")
def startup() -> None:
    runtime.logger.log(
        event_type="startup",
        tools_loaded=len(runtime.registry.list_all()),
        workspace=str(runtime.workspace),
    )


@app.on_event("shutdown")
def shutdown() -> None:
    runtime.logger.log(event_type="shutdown")
