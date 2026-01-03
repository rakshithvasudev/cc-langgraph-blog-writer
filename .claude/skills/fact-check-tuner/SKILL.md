---
name: fact-check-tuner
description: Tune and optimize fact-checking in the research agent. Use when adjusting claim extraction, verification strictness, fixing fact-check loops, reducing API costs, or improving accuracy.
allowed-tools: Read, Edit, Grep
---

# Fact-Checking Optimization

## Overview

The fact-checking system is a two-node loop:

```
write_article → fact_check → [unverified?] → fix_claims → fact_check (max 3x)
                          → [all verified] → approval_article
```

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| `nodes.py` | `fact_check_node` (~line 463) | Extract & verify claims |
| `nodes.py` | `fix_claims_node` (~line 543) | Rewrite unverified claims |
| `prompts.py` | `EXTRACT_CLAIMS_*` | Claim extraction prompts |
| `prompts.py` | `VERIFY_CLAIM_*` | Claim verification prompts |
| `prompts.py` | `FIX_CLAIMS_*` | Article rewriting prompts |

## Tuning Parameters

### Max Fact-Check Iterations

In `fact_check_node` (nodes.py ~line 520):

```python
# Default: 3 iterations
if unverified and fact_check_iteration < 3:
    return Command(goto="fix_claims")
```

**Trade-offs**:
- Higher = more accurate but more API calls
- Lower = faster but may have unverified claims

### Claim Extraction Strictness

Edit `EXTRACT_CLAIMS_SYSTEM` in prompts.py:

**More strict (fewer claims)**:
```python
EXTRACT_CLAIMS_SYSTEM = """Extract ONLY claims that:
1. Cite specific statistics, dates, or numbers
2. Make cause-and-effect assertions
3. Attribute statements to named sources

Skip:
- General observations
- Well-known facts
- Opinions or analysis
- Statements with hedging language ("may", "might", "could")
"""
```

**Less strict (more claims)**:
```python
EXTRACT_CLAIMS_SYSTEM = """Extract all factual assertions including:
1. Any statement presented as fact
2. Comparisons or rankings
3. Historical references
4. Technical specifications
"""
```

### Verification Threshold

Edit `VERIFY_CLAIM_SYSTEM` in prompts.py:

**Strict verification**:
```python
VERIFY_CLAIM_SYSTEM = """Verify claims with HIGH standards:
- Claim must have DIRECT support in sources
- Numbers must match exactly
- Attribution must be to the correct source
- Partial support = NOT verified
"""
```

**Lenient verification**:
```python
VERIFY_CLAIM_SYSTEM = """Verify claims reasonably:
- Accept claims supported by general consensus in sources
- Minor number variations are acceptable
- Paraphrased attributions count as verified
- If claim is generally supported, mark as verified
"""
```

## Cost Optimization

### Current Cost Profile

Per article:
- `fact_check_node`: 2 LLM calls per claim (extract + verify each)
- `fix_claims_node`: 1 LLM call to rewrite article
- Worst case: 3 iterations × (N claims × 2 + 1) calls

### Optimization Strategies

#### 1. Limit Claims Per Article

In `EXTRACT_CLAIMS_USER`:
```python
"""Extract the TOP 10 most important factual claims.
Prioritize claims with specific numbers or statistics."""
```

#### 2. Batch Verification

Modify `fact_check_node` to verify multiple claims in one call:
```python
# Instead of verifying one claim at a time:
for claim in claims:
    verify_response = await llm.ainvoke(verify_single_claim)

# Verify all claims at once:
verify_all_prompt = f"Verify these claims: {claims}\nSources: {sources}"
verify_response = await llm.ainvoke(verify_all_prompt)
```

#### 3. Skip Obvious Facts

Add to `EXTRACT_CLAIMS_SYSTEM`:
```python
"""Skip claims that are:
- Common knowledge (e.g., "Water boils at 100°C")
- Definitions of terms
- Direct quotes already attributed
"""
```

#### 4. Cache Similar Claims

Add caching to `fact_check_node`:
```python
# Simple in-memory cache
_verification_cache = {}

async def fact_check_node(state):
    claim_key = hash(claim["claim"])
    if claim_key in _verification_cache:
        return _verification_cache[claim_key]
    # ... verify and cache result
```

## Improving Accuracy

### Common False Negatives (valid claims marked unverified)

**Problem**: Sources contain the information but LLM misses it

**Fix**: Increase source context in `VERIFY_CLAIM_USER`:
```python
# Instead of truncating at 500 chars
sources_text = "\n".join(
    [f"- {s.get('title', '')}: {s.get('content', '')[:1000]}"
     for s in sources[:15]]  # More sources, more content
)
```

### Common False Positives (invalid claims marked verified)

**Problem**: LLM verifies claims too loosely

**Fix**: Add specific verification criteria:
```python
VERIFY_CLAIM_SYSTEM = """To mark a claim as verified, you MUST find:
1. The exact fact stated in the claim
2. From a source that appears credible
3. With matching details (numbers, dates, names)

If ANY part of the claim is unsupported, mark as NOT verified."""
```

## Debugging Fact-Check Issues

### See what claims are extracted

Add logging to `fact_check_node`:
```python
print(f"Extracted claims: {json.dumps(claims_data, indent=2)}")
```

### See verification results

```python
for result in results:
    print(f"Claim: {result['claim'][:50]}...")
    print(f"  Verified: {result['is_verified']}")
    print(f"  Issue: {result.get('issue', 'None')}")
```

### Test claim extraction alone

```python
import asyncio
from research_agent.graph.nodes import fact_check_node

state = {
    "article": "Your test article with claims...",
    "findings": [],
    "sources": [],
}
result = asyncio.run(fact_check_node(state))
```

## Quick Fixes

### "Too many claims flagged"
→ Make `VERIFY_CLAIM_SYSTEM` more lenient

### "Fact-check taking too long"
→ Reduce max iterations to 1-2
→ Limit claims extracted to 5-10

### "Claims still wrong after fixes"
→ Improve `FIX_CLAIMS_SYSTEM` instructions
→ Provide more source context to fix_claims_node

### "High API costs"
→ Batch verification calls
→ Lower claim extraction count
→ Use faster/cheaper model for verification
