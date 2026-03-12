"""Mashbak agent package."""

def __getattr__(name):
	if name in {"AgentRuntime", "create_runtime"}:
		from . import runtime as _runtime

		return getattr(_runtime, name)
	raise AttributeError(f"module 'agent' has no attribute '{name}'")

__all__ = ["AgentRuntime", "create_runtime"]