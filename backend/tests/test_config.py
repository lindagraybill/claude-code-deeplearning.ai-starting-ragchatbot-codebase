"""Tests for configuration validation.

These tests verify that configuration settings are valid.
The test_max_results_should_be_positive test will FAIL with the current code
because MAX_RESULTS=0 in config.py, which causes all searches to return empty.
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from config import Config, config


class TestConfigValidation:
    """Tests for configuration value validation."""

    def test_max_results_should_be_positive(self):
        """
        MAX_RESULTS must be > 0 for VectorStore.search() to return results.

        This test will FAIL with the current config (MAX_RESULTS=0).
        This is the root cause of 'query failed' errors.
        """
        assert config.MAX_RESULTS > 0, (
            f"MAX_RESULTS is {config.MAX_RESULTS}. "
            "This must be > 0 or VectorStore.search() will always return empty results. "
            "Fix: Change MAX_RESULTS to 5 in backend/config.py line 21."
        )

    def test_max_results_current_value(self):
        """Document the current MAX_RESULTS value for debugging."""
        # This test passes but documents the problematic value
        print(f"\nCurrent MAX_RESULTS value: {config.MAX_RESULTS}")
        assert isinstance(config.MAX_RESULTS, int), "MAX_RESULTS should be an integer"

    def test_chunk_size_is_reasonable(self):
        """CHUNK_SIZE should be between 100 and 2000 characters."""
        assert (
            100 <= config.CHUNK_SIZE <= 2000
        ), f"CHUNK_SIZE={config.CHUNK_SIZE} is outside reasonable range [100, 2000]"

    def test_chunk_overlap_less_than_chunk_size(self):
        """CHUNK_OVERLAP should be less than CHUNK_SIZE."""
        assert config.CHUNK_OVERLAP < config.CHUNK_SIZE, (
            f"CHUNK_OVERLAP ({config.CHUNK_OVERLAP}) should be less than "
            f"CHUNK_SIZE ({config.CHUNK_SIZE})"
        )

    def test_max_history_is_positive(self):
        """MAX_HISTORY should be at least 1 for conversation context."""
        assert (
            config.MAX_HISTORY >= 1
        ), f"MAX_HISTORY={config.MAX_HISTORY} should be >= 1"

    def test_anthropic_model_is_set(self):
        """ANTHROPIC_MODEL should be a non-empty string."""
        assert config.ANTHROPIC_MODEL, "ANTHROPIC_MODEL should not be empty"
        assert isinstance(config.ANTHROPIC_MODEL, str)

    def test_embedding_model_is_set(self):
        """EMBEDDING_MODEL should be a non-empty string."""
        assert config.EMBEDDING_MODEL, "EMBEDDING_MODEL should not be empty"
        assert isinstance(config.EMBEDDING_MODEL, str)


class TestConfigDefaults:
    """Tests verifying default configuration values."""

    def test_default_chunk_size(self):
        """Verify default CHUNK_SIZE is 800."""
        assert config.CHUNK_SIZE == 800

    def test_default_chunk_overlap(self):
        """Verify default CHUNK_OVERLAP is 100."""
        assert config.CHUNK_OVERLAP == 100

    def test_default_max_history(self):
        """Verify default MAX_HISTORY is 2."""
        assert config.MAX_HISTORY == 2

    def test_default_embedding_model(self):
        """Verify default embedding model."""
        assert config.EMBEDDING_MODEL == "all-MiniLM-L6-v2"


class TestConfigCreation:
    """Tests for Config class instantiation."""

    def test_config_dataclass_creation(self):
        """Config can be instantiated as a dataclass."""
        new_config = Config()
        assert hasattr(new_config, "MAX_RESULTS")
        assert hasattr(new_config, "CHUNK_SIZE")
        assert hasattr(new_config, "ANTHROPIC_API_KEY")

    def test_config_values_can_be_overridden(self):
        """Config values can be modified after creation."""
        new_config = Config()
        new_config.MAX_RESULTS = 10
        assert new_config.MAX_RESULTS == 10
