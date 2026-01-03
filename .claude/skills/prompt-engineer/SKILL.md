---
name: prompt-engineer
description: Optimize and test LLM prompts for the research agent. Use when writing prompts, improving prompt quality, debugging LLM responses, fixing JSON parsing issues, or tuning output format.
allowed-tools: Read, Edit, Grep, Glob
---

# Prompt Engineering for Research Agent

## Prompt Location

All prompts are in `src/research_agent/graph/prompts.py`

## Current Prompts

| Prompt Prefix | Used By | Purpose |
|---------------|---------|---------|
| `PLAN_QUERIES_*` | `plan_queries_node` | Generate search queries |
| `ANALYZE_RESULTS_*` | `analyze_results_node` | Extract findings from search results |
| `DECIDE_CONTINUATION_*` | `decide_continuation_node` | Decide if more research needed |
| `SYNTHESIZE_*` | `synthesize_node` | Create article outline |
| `ARTICLE_WRITING_*` | `write_article_node` | Write the full article |
| `EXTRACT_CLAIMS_*` | `fact_check_node` | Extract factual claims |
| `VERIFY_CLAIM_*` | `fact_check_node` | Verify claims against sources |
| `FIX_CLAIMS_*` | `fix_claims_node` | Rewrite unverified claims |

## Prompt Structure Pattern

```python
{NAME}_SYSTEM = """Role and context for the LLM.

Key responsibilities:
1. What to do
2. What to avoid
3. Output constraints

Format requirements:
- JSON structure expectations
- Required fields
"""

{NAME}_USER = """Input context:
{variable1}
{variable2}

Task: Specific instruction

Return JSON:
{{
    "field": "description"
}}"""
```

## Best Practices for This Project

### 1. Always Request JSON Output

```python
# Good - explicit JSON instruction
"""Analyze the results and return JSON:
{
    "findings": [{"summary": "...", "confidence": 0.8}]
}"""

# Bad - ambiguous output format
"""Analyze the results and list the findings."""
```

### 2. Use Double Braces for Literal JSON

```python
# In f-strings or .format(), escape braces:
USER_PROMPT = """Return JSON:
{{
    "topic": "{topic}",
    "count": {count}
}}"""
```

### 3. Add Negative Constraints

```python
SYSTEM = """You are a research analyst.

DO NOT:
- Include personal opinions
- Make claims without source support
- Use em dashes or AI-typical phrases
- Add unnecessary caveats
"""
```

### 4. Specify Output Length

```python
# For summaries
"Provide a 2-3 sentence summary."

# For lists
"Return exactly 5 search queries."

# For articles
"Write approximately 1500 words."
```

## Common Issues & Fixes

### JSON Parsing Fails

**Symptom**: `_parse_json_response()` throws JSONDecodeError

**Fixes**:
1. Add explicit instruction:
```python
"Return ONLY valid JSON. No explanation or markdown."
```

2. Add format example:
```python
"""Return JSON exactly like this:
{"key": "value", "list": ["a", "b"]}"""
```

3. Lower temperature for consistency:
```python
llm = get_llm(temperature=0.1)
```

### Output Too Verbose

**Symptom**: LLM adds explanations around JSON

**Fix**: Add to system prompt:
```python
"Be concise. Return only the requested output format."
```

### Inconsistent Field Names

**Symptom**: Sometimes "summary", sometimes "description"

**Fix**: Show exact field names:
```python
"""Required fields (use exactly these names):
- "summary": string
- "confidence": float between 0 and 1
- "sources": array of strings"""
```

### Claims Not Factual Enough

**Symptom**: Fact-checker flags too many claims

**Fix**: Adjust `EXTRACT_CLAIMS_SYSTEM`:
```python
"Only extract claims that make SPECIFIC factual assertions.
Skip general statements and obvious facts."
```

## Writing Style Enforcement

The `_enforce_writing_style()` function in `nodes.py` post-processes articles.

### Current Rules (line ~56-90 in nodes.py)

```python
# Em dash replacement
text = re.sub(r"\s*[—–-]{2,}\s*", ", ", text)
text = re.sub(r"—", ", ", text)

# AI phrase removal
replacements = [
    (r"In today's (?:world|society|age)", "Currently"),
    (r"In the realm of", "In"),
    (r"\bdelve into\b", "explore"),
    (r"\bleverage\b", "use"),
    # ... more patterns
]
```

### Adding New Rules

Edit the `replacements` list:
```python
replacements = [
    # Existing rules...

    # Add new rules:
    (r"(?i)\bsynergy\b", "combination"),
    (r"(?i)\bholistic\b", "comprehensive"),
    (r"(?i)\bparadigm shift\b", "major change"),
]
```

## Testing Prompts

### Quick Test via Python

```python
import asyncio
from research_agent.services.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

async def test_prompt():
    llm = get_llm()
    messages = [
        SystemMessage(content="Your system prompt"),
        HumanMessage(content="Your user prompt"),
    ]
    response = await llm.ainvoke(messages)
    print(response.content)

asyncio.run(test_prompt())
```

### Test with Full Graph

```bash
langgraph dev
# Then use Studio UI to run with test input
```

## Prompt Optimization Checklist

- [ ] Clear role definition in system prompt
- [ ] Explicit output format with example
- [ ] Negative constraints (what NOT to do)
- [ ] Double braces for literal JSON in templates
- [ ] Temperature appropriate for task (0.1-0.3 for structured, 0.5-0.7 for creative)
- [ ] Length guidance if applicable
- [ ] Field names match what code expects
- [ ] Tested with edge cases (empty input, long input)
