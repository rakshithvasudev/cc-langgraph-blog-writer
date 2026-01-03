"""Tests for API routes."""

import pytest


def test_root_endpoint(client):
    """Test the root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Research Agent API"
    assert "endpoints" in data


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_start_research_valid_request(client, sample_topic):
    """Test starting a research task with valid parameters."""
    response = client.post(
        "/research/start",
        json={
            "topic": sample_topic,
            "review_mode": "autonomous",
            "max_iterations": 7,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "thread_id" in data
    assert data["topic"] == sample_topic
    assert data["phase"] == "planning"
    assert data["max_iterations"] == 7


def test_start_research_default_values(client, sample_topic):
    """Test starting research with default values."""
    response = client.post(
        "/research/start",
        json={"topic": sample_topic},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["max_iterations"] == 7


def test_start_research_invalid_iterations(client, sample_topic):
    """Test that invalid iteration counts are rejected."""
    response = client.post(
        "/research/start",
        json={
            "topic": sample_topic,
            "max_iterations": 3,  # Below minimum of 5
        },
    )
    assert response.status_code == 422  # Validation error


def test_start_research_empty_topic(client):
    """Test that empty topics are rejected."""
    response = client.post(
        "/research/start",
        json={"topic": ""},
    )
    assert response.status_code == 422


def test_get_status_not_found(client):
    """Test getting status for non-existent thread."""
    response = client.get("/research/nonexistent-thread-id/status")
    assert response.status_code == 404


def test_get_pending_approval_not_found(client):
    """Test getting pending approval for non-existent thread."""
    response = client.get("/research/nonexistent-thread-id/pending-approval")
    assert response.status_code == 404


def test_get_result_not_found(client):
    """Test getting result for non-existent thread."""
    response = client.get("/research/nonexistent-thread-id/result")
    assert response.status_code == 404


def test_cancel_research(client):
    """Test cancelling a research task."""
    response = client.delete("/research/some-thread-id")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


def test_list_research_tasks_empty(client):
    """Test listing research tasks when none exist."""
    response = client.get("/research/")
    assert response.status_code == 200
    assert response.json() == []


def test_review_modes(client, sample_topic):
    """Test all review modes are accepted."""
    modes = ["autonomous", "review_before_writing", "review_at_each_stage"]

    for mode in modes:
        response = client.post(
            "/research/start",
            json={
                "topic": sample_topic,
                "review_mode": mode,
            },
        )
        assert response.status_code == 200, f"Failed for mode: {mode}"
