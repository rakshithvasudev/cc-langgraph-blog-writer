---
name: langgraph-dev
description: Run, test, and debug the LangGraph research agent. Use when starting the server, running tests, debugging graph execution, fixing graph errors, or checking server status.
---

# LangGraph Development

Quick reference for running and debugging the research agent.

## Quick Commands

### Start Development Server

```bash
cd /home/rajathdb/research_agent && langgraph dev
```

Server runs at:
- API: http://127.0.0.1:2024
- Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- API Docs: http://127.0.0.1:2024/docs

### Run Tests

```bash
# All tests
cd /home/rajathdb/research_agent && pytest tests -v

# Specific test file
pytest tests/test_graph/test_nodes.py -v

# Specific test
pytest tests/test_graph/test_nodes.py::test_plan_queries_node -v

# With coverage
pytest tests --cov=research_agent --cov-report=term-missing
```

### Check Server Logs

```bash
# If running in background, check output file
tail -f /tmp/claude/-home-rajathdb/tasks/*.output
```

## Environment Setup

Required environment variables in `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...

# Optional
LLM_MODEL=claude-sonnet-4-20250514
LLM_TEMPERATURE=0.7
```

## Graph Structure

```
START
  ↓
plan_queries → approval_queries → execute_search → analyze_results
                                        ↑                ↓
                                        └──────── decide_continuation
                                                         ↓
                          ┌──────────────────────────────┴──────────┐
                          ↓                                         ↓
                   plan_queries (loop)                      approval_findings
                                                                    ↓
                                                               synthesize
                                                                    ↓
                                                              write_article
                                                                    ↓
                                                               fact_check ←──┐
                                                                    ↓        │
                                                         ┌──────────┴────────┤
                                                         ↓                   │
                                                   fix_claims ───────────────┘
                                                         ↓
                                                 approval_article
                                                         ↓
                                                     complete
                                                         ↓
                                                        END
```

## Common Errors & Solutions

### InvalidUpdateError: Can receive only one value per step

**Cause**: Multiple nodes updating the same field in parallel (duplicate edges)

**Fix**:
1. Remove duplicate edges from builder.py
2. Use `Command` for conditional routing instead of multiple edges
3. For list fields, use `Annotated[list[T], add]` reducer in state.py

### KeyError when accessing state

**Cause**: Direct state access like `state["field"]` fails when field is missing

**Fix**: Always use `.get()` with defaults:
```python
# Bad
topic = state["topic"]

# Good
topic = state.get("topic", "")
```

### Graph stuck at interrupt

**Cause**: Human-in-the-loop node waiting for input

**Fix**: In Studio UI, provide the expected approval format:
```json
{"approved": true}
```

Or to reject:
```json
{"approved": false, "reason": "Needs more research"}
```

### BlockingError: Synchronous blocking call

**Cause**: Using synchronous HTTP client in async context

**Fix**: Use async clients:
```python
# Bad
from tavily import TavilyClient
client = TavilyClient()
results = client.search(query)  # Blocks!

# Good
from tavily import AsyncTavilyClient
client = AsyncTavilyClient()
results = await client.search(query)  # Async!
```

### RecursionError in SSL

**Cause**: Synchronous `requests` library conflicts with async event loop

**Fix**: Use `httpx` or async clients instead of `requests`

## State Fields Reference

| Field | Type | Reducer | Description |
|-------|------|---------|-------------|
| `topic` | str | - | Research topic |
| `review_mode` | ReviewMode | - | autonomous/review_before_writing/review_at_each_stage |
| `max_iterations` | int | - | Max research cycles (default 7) |
| `sources` | list[Source] | add | Accumulated web sources |
| `findings` | list[Finding] | add | Extracted research findings |
| `planned_queries` | list[SearchQuery] | - | Current batch of queries |
| `article` | str | - | Generated article |
| `fact_check_results` | list[FactCheckResult] | - | Claim verification results |
| `current_phase` | ResearchPhase | - | Current execution phase |

## Testing in Studio

1. Start server: `langgraph dev`
2. Open Studio URL in browser
3. Create new thread (important: don't reuse corrupted threads!)
4. Input format:
```json
{
  "topic": "Your research topic here",
  "review_mode": "autonomous",
  "max_iterations": 5
}
```

## Debugging Tips

### View graph visualization
Studio UI shows the graph structure. If nodes appear disconnected, check:
- `Command[Literal[...]]` type annotations on routing nodes
- No duplicate edges from same source node

### Check which node is running
Server logs show: `langgraph_node=node_name`

### Inspect state at any point
In Studio, click on a node to see its input/output state

### Force restart with clean state
1. Stop server (Ctrl+C)
2. Start fresh: `langgraph dev`
3. Create NEW thread in Studio (don't resume old ones)
