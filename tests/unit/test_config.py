import os
from unittest.mock import mock_open, patch

import pytest

from argus.config import ConfigurationError, load_config


def test_load_config_defaults():
    """Test loading configuration with defaults (no file, no env)."""
    with patch("pathlib.Path.exists", return_value=False):
        # Should raise ConfigurationError because database section is missing
        with pytest.raises(ConfigurationError):
            load_config()


def test_load_config_missing_required():
    """Test that missing required fields raises ConfigurationError."""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(ConfigurationError):
            load_config()


def test_load_config_from_env():
    """Test loading configuration purely from environment variables."""
    with (
        patch.dict(
            os.environ, {"ARGUS_DATABASE_DSN": "postgres://user:pass@localhost:5432/db"}
        ),
        patch("pathlib.Path.exists", return_value=False),
    ):
        config = load_config()
        assert config.database.dsn == "postgres://user:pass@localhost:5432/db"


def test_load_config_from_file():
    """Test loading configuration from a TOML file."""
    toml_content = b"""
    [database]
    dsn = "postgres://file:5432/db"

    [sandbox]
    image = "postgres:15-alpine"
    """
    with (
        patch("builtins.open", mock_open(read_data=toml_content)),
        patch("pathlib.Path.exists", return_value=True),
    ):
        config = load_config()
        assert config.database.dsn == "postgres://file:5432/db"
        assert config.sandbox.image == "postgres:15-alpine"


def test_load_config_env_override():
    """Test that environment variables override file configuration."""
    toml_content = b"""
    [database]
    dsn = "postgres://file:5432/db"
    """
    with (
        patch.dict(os.environ, {"ARGUS_DATABASE_DSN": "postgres://env:5432/db"}),
        patch("builtins.open", mock_open(read_data=toml_content)),
        patch("pathlib.Path.exists", return_value=True),
    ):
        config = load_config()
        assert config.database.dsn == "postgres://env:5432/db"
