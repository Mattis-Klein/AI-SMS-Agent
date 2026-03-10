"""Configuration loader and manager"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Configuration loader"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self._config = {}
        if config_path:
            self.load()
    
    def load(self) -> None:
        """Load configuration from JSON file"""
        if not self.config_path or not self.config_path.exists():
            self._config = {}
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except Exception as e:
            print(f"[config] Warning: Failed to load {self.config_path}: {e}")
            self._config = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default
    
    def get_allowed_directories(self) -> list:
        """Get explicit safe directory allowlist for path-based tools."""
        dirs = self.get("allowed_directories", [])
        return [Path(d) if isinstance(d, str) else d for d in dirs]
    
    def get_allowed_tools(self) -> list:
        """Get list of allowed tool names (if restricted)"""
        tools = self.get("allowed_tools")
        if tools is None:
            return None  # None = all tools allowed
        return tools
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.get("logging", {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        return self.get("security", {})
