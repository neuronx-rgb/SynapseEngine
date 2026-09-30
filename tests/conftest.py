"""
tests/conftest.py
Shared pytest fixtures.
"""
import os
import sys
import pytest

# Ensure MOCK_MODE is true for all tests
os.environ["MOCK_MODE"] = "true"
os.environ["DATA_DIR"] = "./data/test"

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def ensure_mock_mode():
    """Auto-use fixture to guarantee MOCK_MODE for every test."""
    old = os.environ.get("MOCK_MODE")
    # Don't override if a test explicitly sets MOCK_MODE=false
    yield
    if old is not None:
        os.environ["MOCK_MODE"] = old
