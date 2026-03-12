"""Configuration loader for Mashbak master environment file.

Loads .env.master from the project root and exposes configuration variables
consistently across the system. Supports fallback to OS environment variables.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None


class ConfigLoader:
    """Load and cache configuration from .env.master."""
    
    _config_cache: Optional[dict] = None
    _master_env_path: Optional[Path] = None
    
    @classmethod
    def _get_master_env_path(cls) -> Path:
        """Get path to .env.master file in project root."""
        if cls._master_env_path:
            return cls._master_env_path
        
        # Start from this file's directory and resolve mashbak platform root.
        platform_root = Path(__file__).resolve().parent.parent  # mashbak/
        master_path = platform_root / ".env.master"  # mashbak/.env.master
        
        return master_path
    
    @classmethod
    def load(cls, reload: bool = False) -> dict:
        """
        Load configuration from .env.master.
        
        Returns dictionary of configuration variables with OS environment
        as fallback.
        """
        if cls._config_cache and not reload:
            return cls._config_cache
        
        config = {}
        master_path = cls._get_master_env_path()
        
        # Try to load from .env.master using dotenv
        if dotenv_values and master_path.exists():
            try:
                env_dict = dotenv_values(str(master_path))
                if env_dict:
                    config.update(env_dict)
            except Exception as e:
                print(f"Warning: Could not load {master_path}: {e}")
        
        # Fall back to OS environment variables
        # This allows docker/shell overrides to work
        for key in list(config.keys()):
            if key in os.environ:
                config[key] = os.environ[key]
        
        # Also add any OS env vars not in the master config
        for key, value in os.environ.items():
            if key not in config:
                config[key] = value
        
        cls._config_cache = config
        return config
    
    @classmethod
    def get(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a configuration variable."""
        config = cls.load()
        return config.get(key, default)
    
    @classmethod
    def getenv(cls, key: str, default: Optional[str] = None) -> Optional[str]:
        """Alias for get() to match os.getenv() interface."""
        return cls.get(key, default)
    
    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        """Get a boolean configuration variable."""
        value = cls.get(key, "").strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        return default
    
    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """Get an integer configuration variable."""
        try:
            return int(cls.get(key) or default)
        except (ValueError, TypeError):
            return default

    @classmethod
    def get_float(cls, key: str, default: float = 0.0) -> float:
        """Get a float configuration variable."""
        try:
            return float(cls.get(key) or default)
        except (ValueError, TypeError):
            return default


def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Convenience function to get a configuration variable.
    
    Usage:
        from agent.config_loader import get_config
        api_key = get_config("OPENAI_API_KEY")
    """
    return ConfigLoader.get(key, default)


def get_config_bool(key: str, default: bool = False) -> bool:
    """Get a boolean configuration variable."""
    return ConfigLoader.get_bool(key, default)


def get_config_int(key: str, default: int = 0) -> int:
    """Get an integer configuration variable."""
    return ConfigLoader.get_int(key, default)


def get_config_float(key: str, default: float = 0.0) -> float:
    """Get a float configuration variable."""
    return ConfigLoader.get_float(key, default)


# Initialize config on import
ConfigLoader.load()
