---
name: test-generator
description: Generate pytest tests for research agent components. Use when writing tests, adding test coverage, creating test fixtures, or testing new nodes and API endpoints.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# Test Generation for Research Agent

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_graph/
│   ├── test_nodes.py        # Node unit tests
│   └── test_builder.py      # Graph construction tests
└── test_api/
    └── test_routes.py       # API integration tests
```

## Running Tests

```bash
# All tests
pytest tests -v

# Specific file
pytest tests/test_graph/test_nodes.py -v

# Specific test
pytest tests/test_graph/test_nodes.py::test_plan_queries_node -v

# With coverage
pytest tests --cov=research_agent --cov-report=term-missing

# Stop on first failure
pytest tests -x

# Show print statements
pytest tests -s
```

## Node Test Template

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from research_agent.graph.nodes import {name}_node
from research_agent.graph.state import ResearchState
from research_agent.models.enums import ReviewMode, ResearchPhase


@pytest.mark.asyncio
async def test_{name}_node_basic():
    """Test {name} node with valid input."""
    state: ResearchState = {
        "topic": "artificial intelligence trends",
        "review_mode": ReviewMode.AUTONOMOUS,
        "max_iterations": 7,
        "current_iteration": 0,
        "findings": [],
        "sources": [],
        # Add other required fields
    }

    # Mock LLM response
    mock_response = MagicMock()
    mock_response.content = '''```json
    {
        "expected_field": "expected_value"
    }
    ```'''

    with patch("research_agent.graph.nodes.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = await {name}_node(state)

    assert "expected_field" in result
    assert result["expected_field"] == "expected_value"


@pytest.mark.asyncio
async def test_{name}_node_empty_state():
    """Test {name} node handles minimal state gracefully."""
    state: ResearchState = {
        "topic": "",
    }

    mock_response = MagicMock()
    mock_response.content = '{"result": []}'

    with patch("research_agent.graph.nodes.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = await {name}_node(state)

    # Should not raise, should handle gracefully
    assert result is not None


@pytest.mark.asyncio
async def test_{name}_node_malformed_response():
    """Test {name} node handles malformed LLM response."""
    state: ResearchState = {
        "topic": "test topic",
    }

    mock_response = MagicMock()
    mock_response.content = "This is not valid JSON at all"

    with patch("research_agent.graph.nodes.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        with pytest.raises(json.JSONDecodeError):
            await {name}_node(state)
```

## Command Node Test Template

For nodes that return `Command`:

```python
from langgraph.types import Command

@pytest.mark.asyncio
async def test_{name}_node_routes_to_next():
    """Test {name} node routes correctly when condition met."""
    state: ResearchState = {
        "topic": "test",
        "condition_field": True,
    }

    mock_response = MagicMock()
    mock_response.content = '{"decision": "proceed"}'

    with patch("research_agent.graph.nodes.get_llm") as mock_get_llm:
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        result = await {name}_node(state)

    assert isinstance(result, Command)
    assert result.goto == "expected_next_node"


@pytest.mark.asyncio
async def test_{name}_node_routes_to_alternate():
    """Test {name} node routes to alternate when condition not met."""
    state: ResearchState = {
        "topic": "test",
        "condition_field": False,
    }

    result = await {name}_node(state)

    assert isinstance(result, Command)
    assert result.goto == "alternate_node"
```

## API Route Test Template

```python
import pytest
from fastapi.testclient import TestClient

from research_agent.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_{endpoint}_success(client):
    """Test {endpoint} with valid input."""
    response = client.post(
        "/api/{endpoint}",
        json={
            "topic": "test topic",
            "review_mode": "autonomous",
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data


def test_{endpoint}_validation_error(client):
    """Test {endpoint} rejects invalid input."""
    response = client.post(
        "/api/{endpoint}",
        json={
            # Missing required field
        }
    )

    assert response.status_code == 422  # Validation error


def test_{endpoint}_not_found(client):
    """Test {endpoint} handles missing resource."""
    response = client.get("/api/{endpoint}/nonexistent-id")

    assert response.status_code == 404
```

## Fixture Templates

Add to `tests/conftest.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from research_agent.graph.state import ResearchState
from research_agent.models.enums import ReviewMode, ResearchPhase
from research_agent.models.research import Source, Finding


@pytest.fixture
def sample_state() -> ResearchState:
    """Create a sample research state for testing."""
    return {
        "topic": "artificial intelligence",
        "review_mode": ReviewMode.AUTONOMOUS,
        "max_iterations": 7,
        "current_iteration": 0,
        "current_phase": ResearchPhase.PLANNING,
        "planned_queries": [],
        "current_query_index": 0,
        "sources": [],
        "findings": [],
        "outline": "",
        "article": "",
        "fact_check_results": [],
        "fact_check_passed": False,
        "fact_check_iteration": 0,
        "error_message": None,
    }


@pytest.fixture
def sample_sources() -> list[Source]:
    """Create sample sources for testing."""
    return [
        {
            "url": "https://example.com/article1",
            "title": "AI Trends 2024",
            "content": "Artificial intelligence is transforming...",
            "score": 0.95,
        },
        {
            "url": "https://example.com/article2",
            "title": "Machine Learning Guide",
            "content": "Machine learning models are...",
            "score": 0.87,
        },
    ]


@pytest.fixture
def sample_findings() -> list[Finding]:
    """Create sample findings for testing."""
    return [
        {
            "summary": "AI adoption increased 50% in 2024",
            "supporting_sources": ["https://example.com/article1"],
            "confidence": 0.9,
            "topic_area": "adoption",
        },
    ]


@pytest.fixture
def mock_llm():
    """Create a mock LLM for testing."""
    mock = AsyncMock()
    mock.ainvoke.return_value = MagicMock(content='{"result": "test"}')
    return mock


@pytest.fixture
def mock_search_service():
    """Create a mock search service for testing."""
    mock = AsyncMock()
    mock.search.return_value = [
        {
            "url": "https://example.com",
            "title": "Test Result",
            "content": "Test content...",
            "score": 0.9,
        }
    ]
    return mock
```

## Testing Patterns

### Mock LLM Calls

```python
with patch("research_agent.graph.nodes.get_llm") as mock_get_llm:
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"key": "value"}'
    )
    mock_get_llm.return_value = mock_llm

    result = await some_node(state)
```

### Mock Search Service

```python
with patch("research_agent.graph.nodes.get_search_service") as mock_get_search:
    mock_service = AsyncMock()
    mock_service.search.return_value = [{"url": "...", "content": "..."}]
    mock_get_search.return_value = mock_service

    result = await execute_search_node(state)
```

### Test Async Functions

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

### Test Exceptions

```python
@pytest.mark.asyncio
async def test_raises_on_invalid_input():
    with pytest.raises(ValueError, match="expected error message"):
        await function_that_raises(invalid_input)
```

## Coverage Goals

Aim for:
- 80%+ coverage on `nodes.py`
- 90%+ coverage on `prompts.py` (mostly constants)
- 70%+ coverage on API routes
- 100% coverage on utility functions

Check coverage:
```bash
pytest tests --cov=research_agent --cov-report=html
open htmlcov/index.html
```
