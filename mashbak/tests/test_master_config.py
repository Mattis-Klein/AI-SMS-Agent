"""Tests for master configuration file loading."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.config_loader import ConfigLoader, get_config, get_config_bool, get_config_int


def test_config_loader_basic_loading():
    """Test that ConfigLoader can load basic configuration."""
    # Create temp .env.master file
    with tempfile.TemporaryDirectory() as tmpdir:
        test_master_path = Path(tmpdir) / ".env.master"
        test_master_path.write_text(
            "TEST_VAR=test_value\n"
            "TEST_BOOL=true\n"
            "TEST_INT=42\n"
        )
        
        # Override the path getter
        original_method = ConfigLoader._get_master_env_path
        ConfigLoader._get_master_env_path = classmethod(lambda cls: test_master_path)
        ConfigLoader._config_cache = None  # Reset cache
        
        try:
            # Load config
            config = ConfigLoader.load()
            assert "TEST_VAR" in config
            assert config["TEST_VAR"] == "test_value"
            print("✓ ConfigLoader loaded basic variables")
        finally:
            ConfigLoader._get_master_env_path = original_method
            ConfigLoader._config_cache = None


def test_config_loader_type_conversion():
    """Test ConfigLoader type conversion methods."""
    # Set environment variables directly for testing
    os.environ["TEST_BOOL_TRUE"] = "true"
    os.environ["TEST_BOOL_FALSE"] = "false"
    os.environ["TEST_INT"] = "123"
    
    try:
        assert get_config_bool("TEST_BOOL_TRUE") is True
        print("✓ get_config_bool returned True for 'true'")
        
        assert get_config_bool("TEST_BOOL_FALSE") is False
        print("✓ get_config_bool returned False for 'false'")
        
        assert get_config_int("TEST_INT") == 123
        print("✓ get_config_int returned 123")
    finally:
        # Clean up
        os.environ.pop("TEST_BOOL_TRUE", None)
        os.environ.pop("TEST_BOOL_FALSE", None)
        os.environ.pop("TEST_INT", None)


def test_config_loader_default_values():
    """Test ConfigLoader returns defaults for missing vars."""
    missing_val = get_config("NONEXISTENT_VAR", default="default_value")
    assert missing_val == "default_value"
    print("✓ get_config returned default for missing variable")
    
    missing_bool = get_config_bool("NONEXISTENT_BOOL", default=True)
    assert missing_bool is True
    print("✓ get_config_bool returned default True for missing variable")
    
    missing_int = get_config_int("NONEXISTENT_INT", default=999)
    assert missing_int == 999
    print("✓ get_config_int returned default 999 for missing variable")


def test_config_loader_env_fallback():
    """Test ConfigLoader falls back to OS environment variables."""
    os.environ["FALLBACK_TEST"] = "from_os_env"
    
    try:
        # Create empty master file
        with tempfile.TemporaryDirectory() as tmpdir:
            test_master_path = Path(tmpdir) / ".env.master"
            test_master_path.write_text("OTHER_VAR=other_value\n")
            
            original_method = ConfigLoader._get_master_env_path
            ConfigLoader._get_master_env_path = classmethod(lambda cls: test_master_path)
            ConfigLoader._config_cache = None  # Reset cache
            
            try:
                config = ConfigLoader.load()
                # Should include OS env variable
                assert config.get("FALLBACK_TEST") == "from_os_env"
                print("✓ ConfigLoader fell back to OS environment variable")
            finally:
                ConfigLoader._get_master_env_path = original_method
                ConfigLoader._config_cache = None
    finally:
        os.environ.pop("FALLBACK_TEST", None)


if __name__ == "__main__":
    print("\n=== Testing Master Configuration Loader ===")
    test_config_loader_basic_loading()
    test_config_loader_type_conversion()
    test_config_loader_default_values()
    test_config_loader_env_fallback()
    print("\n✅ All configuration loader tests passed!")
