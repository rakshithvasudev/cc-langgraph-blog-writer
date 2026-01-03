---
name: graph-node-generator
description: Generate new LangGraph nodes for the research agent. Use when adding nodes, creating graph functions, extending the research workflow, or scaffolding new graph components.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# Graph Node Generator

Automates creation of new nodes for the research agent graph.

## File Locations

| File | Purpose |
|------|---------|
| `src/research_agent/graph/nodes.py` | Node implementations |
| `src/research_agent/graph/prompts.py` | System/user prompts |
| `src/research_agent/graph/builder.py` | Graph construction |
| `src/research_agent/graph/state.py` | State schema |
| `tests/test_graph/test_nodes.py` | Node tests |

## Step-by-Step Process

### 1. Create the Node Function

Add to `src/research_agent/graph/nodes.py`:

```python
async def {name}_node(state: ResearchState) -> dict:
    """Description of what this node does."""
    llm = get_llm()

    # Extract state with .get() defaults (IMPORTANT for LangGraph Studio)
    topic = state.get("topic", "")
    findings = state.get("findings", [])

    messages = [
        SystemMessage(content={NAME}_SYSTEM),
        HumanMessage(content={NAME}_USER.format(topic=topic)),
    ]

    response = await llm.ainvoke(messages)
    result = _parse_json_response(response.content)

    return {
        "field_to_update": result,
    }
```

### 2. For Conditional Routing Nodes

Use `Command` with type annotation:

```python
async def {name}_node(
    state: ResearchState,
) -> Command[Literal["next_node_a", "next_node_b"]]:
    """Node with conditional routing."""
    # ... logic ...

    if condition:
        return Command(goto="next_node_a")
    else:
        return Command(
            update={"some_field": value},
            goto="next_node_b"
        )
```

### 3. For Human-in-the-Loop Nodes

Use `interrupt()`:

```python
from langgraph.types import Command, interrupt

async def approval_{name}_node(
    state: ResearchState,
) -> Command[Literal["proceed", "reject"]]:
    """Pause for human approval."""
    review_mode = state.get("review_mode", ReviewMode.AUTONOMOUS)

    if review_mode == ReviewMode.AUTONOMOUS:
        return Command(goto="proceed")

    approval = interrupt({
        "type": "{name}_approval",
        "data": state.get("data_to_review", []),
        "message": "Please review and approve.",
    })

    if approval.get("approved"):
        return Command(goto="proceed")
    else:
        return Command(
            update={"error_message": approval.get("reason", "Rejected")},
            goto="handle_error"
        )
```

### 4. Add Prompts

Add to `src/research_agent/graph/prompts.py`:

```python
{NAME}_SYSTEM = """You are a specialized assistant for {task}.

Your responsibilities:
1. First responsibility
2. Second responsibility

Output format:
- Always return valid JSON
- Include required fields: field1, field2
"""

{NAME}_USER = """Context:
Topic: {topic}
Previous findings: {findings}

Task: {specific_task}

Return JSON with the following structure:
{{
    "field1": "value",
    "field2": ["item1", "item2"]
}}"""
```

### 5. Register in Builder

Add to BOTH functions in `src/research_agent/graph/builder.py`:

```python
# In build_research_graph() AND _build_graph_for_cli():

# Add node
builder.add_node("{name}", {name}_node)

# Add edges
builder.add_edge("previous_node", "{name}")  # Incoming edge
# For conditional nodes: NO outgoing edge - Command handles it
# For simple nodes:
builder.add_edge("{name}", "next_node")  # Outgoing edge
```

### 6. Update State (if needed)

Add new fields to `src/research_agent/graph/state.py`:

```python
class ResearchState(TypedDict):
    # ... existing fields ...

    # For simple fields:
    new_field: str

    # For accumulated lists (multiple nodes can append):
    new_list: Annotated[list[NewType], add]
```

### 7. Create Tests

Add to `tests/test_graph/test_nodes.py`:

```python
@pytest.mark.asyncio
async def test_{name}_node_basic():
    """Test {name} node with valid input."""
    state: ResearchState = {
        "topic": "test topic",
        # Add required fields with realistic test data
    }

    result = await {name}_node(state)

    assert "expected_field" in result
    assert isinstance(result["expected_field"], expected_type)


@pytest.mark.asyncio
async def test_{name}_node_empty_state():
    """Test {name} node handles empty state gracefully."""
    state: ResearchState = {"topic": ""}

    result = await {name}_node(state)

    # Should not raise, should return sensible defaults
    assert result is not None
```

## Common Patterns in This Codebase

### JSON Parsing
Always use the helper function:
```python
result = _parse_json_response(response.content)
```

### Writing Style Enforcement
For text output nodes, apply style rules:
```python
text = _enforce_writing_style(response.content)
```

### State Access
Always use `.get()` with defaults:
```python
# Good
topic = state.get("topic", "")
findings = state.get("findings", [])

# Bad - will fail in LangGraph Studio
topic = state["topic"]
```

## Checklist

- [ ] Node function created with proper async signature
- [ ] State accessed with `.get()` defaults
- [ ] Prompts added to prompts.py
- [ ] Node registered in `build_research_graph()`
- [ ] Node registered in `_build_graph_for_cli()`
- [ ] Edges defined (or Command routing for conditional)
- [ ] State schema updated if new fields needed
- [ ] Tests written for happy path and edge cases
- [ ] Import added to nodes.py imports section
- [ ] Import added to builder.py imports section
