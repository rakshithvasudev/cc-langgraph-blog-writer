"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from research_agent.api.dependencies import reset_graph
from research_agent.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    reset_graph()  # Ensure fresh graph for each test
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_topic():
    """Sample research topic for testing."""
    return "The impact of artificial intelligence on healthcare diagnostics"
