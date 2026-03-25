import os
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests that make real API calls"
    )


@pytest.fixture
def has_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
