"""Graph node implementations for the research agent."""

import json
import re
from datetime import datetime
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command, interrupt

from ..models.enums import ResearchPhase, ReviewMode
from ..models.research import FactCheckResult, Finding, SearchQuery
from ..services.llm import get_llm
from ..services.search import get_search_service
from .prompts import (
    ANALYZE_RESULTS_SYSTEM,
    ANALYZE_RESULTS_USER,
    ARTICLE_WRITING_SYSTEM,
    ARTICLE_WRITING_USER,
    DECIDE_CONTINUATION_SYSTEM,
    DECIDE_CONTINUATION_USER,
    EXTRACT_CLAIMS_SYSTEM,
    EXTRACT_CLAIMS_USER,
    FIX_CLAIMS_SYSTEM,
    FIX_CLAIMS_USER,
    GRAMMAR_CHECK_SYSTEM,
    GRAMMAR_CHECK_USER,
    PLAN_QUERIES_SYSTEM,
    PLAN_QUERIES_USER,
    SYNTHESIZE_SYSTEM,
    SYNTHESIZE_USER,
    VERIFY_CLAIM_SYSTEM,
    VERIFY_CLAIM_USER,
)
from .state import ResearchState


def _parse_json_response(content: str) -> dict | list:
    """Extract and parse JSON from LLM response."""
    # Try to find JSON in the response
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if json_match:
        content = json_match.group(1)

    # Try parsing directly
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to find array or object pattern
        array_match = re.search(r"\[[\s\S]*\]", content)
        if array_match:
            return json.loads(array_match.group())
        obj_match = re.search(r"\{[\s\S]*\}", content)
        if obj_match:
            return json.loads(obj_match.group())
        raise


def _enforce_writing_style(text: str) -> str:
    """Post-process text to enforce human writing style."""
    # Replace em dashes with appropriate punctuation
    text = re.sub(r"\s*[—–-]{2,}\s*", ", ", text)  # Multiple dashes to comma
    text = re.sub(r"—", ", ", text)  # Unicode em dash
    text = re.sub(r"–", ", ", text)  # Unicode en dash

    # Fix common AI phrases
    replacements = [
        (r"In today's (?:world|society|age)", "Currently"),
        (r"In the realm of", "In"),
        (r"It's important to note that", "Note that"),
        (r"It's worth mentioning that", "Also,"),
        (r"It is important to note that", "Note that"),
        (r"It is worth mentioning that", "Also,"),
        (r"\bdelve into\b", "explore"),
        (r"\bdive deep into\b", "examine"),
        (r"\bleverage\b", "use"),
        (r"\butilize\b", "use"),
        (r"In conclusion,", ""),
        (r"To summarize,", ""),
        (r"\bcrucial\b", "important"),
        (r"\bvital\b", "important"),
        (r"the landscape of", ""),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Clean up double spaces and extra commas
    text = re.sub(r"  +", " ", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s+\.", ".", text)

    return text.strip()


# =============================================================================
# RESEARCH NODES
# =============================================================================


async def plan_queries_node(state: ResearchState) -> dict:
    """Generate search queries based on the research topic."""
    llm = get_llm()

    topic = state.get("topic", "")
    findings = state.get("findings", [])

    # Build context from previous findings if any
    context = ""
    if findings:
        context = f"We have already found {len(findings)} findings. Generate queries to fill gaps."
        if state.get("continuation_rationale"):
            context += f"\nGaps to address: {state['continuation_rationale']}"

    messages = [
        SystemMessage(content=PLAN_QUERIES_SYSTEM),
        HumanMessage(
            content=PLAN_QUERIES_USER.format(topic=topic, context=context)
        ),
    ]

    response = await llm.ainvoke(messages)
    queries_data = _parse_json_response(response.content)

    planned_queries: list[SearchQuery] = []
    for q in queries_data:
        planned_queries.append(
            SearchQuery(
                query=q["query"],
                rationale=q.get("rationale", ""),
                executed=False,
            )
        )

    return {
        "planned_queries": planned_queries,
        "current_query_index": 0,
        "current_phase": ResearchPhase.SEARCHING,
    }


async def approval_queries_node(
    state: ResearchState,
) -> Command[Literal["execute_search", "handle_error"]]:
    """Pause for human approval of planned queries if required."""
    review_mode = state.get("review_mode", ReviewMode.AUTONOMOUS)
    planned_queries = state.get("planned_queries", [])

    if review_mode != ReviewMode.REVIEW_AT_EACH_STAGE:
        return Command(goto="execute_search")

    approval = interrupt(
        {
            "type": "queries_approval",
            "queries": planned_queries,
            "message": "Please review and approve the planned search queries.",
            "instructions": "You may modify queries or reject them entirely.",
        }
    )

    if approval.get("approved"):
        modified_queries = approval.get("modified_queries", planned_queries)
        return Command(update={"planned_queries": modified_queries}, goto="execute_search")
    else:
        return Command(
            update={"error_message": approval.get("reason", "Queries rejected")},
            goto="handle_error",
        )


async def execute_search_node(state: ResearchState) -> dict:
    """Execute current search query using Tavily."""
    search_service = get_search_service()

    planned_queries = state.get("planned_queries", [])
    query_index = state.get("current_query_index", 0)

    # Get current query
    if query_index >= len(planned_queries):
        # No more queries to execute
        return {"current_phase": ResearchPhase.ANALYZING}

    current_query = planned_queries[query_index]

    # Execute search
    sources = await search_service.search(current_query["query"])

    # Mark query as executed
    updated_queries = planned_queries.copy()
    updated_queries[query_index] = SearchQuery(
        query=current_query["query"],
        rationale=current_query.get("rationale", ""),
        executed=True,
    )

    return {
        "sources": sources,  # Will be accumulated via reducer
        "planned_queries": updated_queries,
        "current_query_index": query_index + 1,
    }


async def analyze_results_node(state: ResearchState) -> dict:
    """Analyze search results and extract findings."""
    llm = get_llm()

    sources = state.get("sources", [])
    planned_queries = state.get("planned_queries", [])
    current_query_index = state.get("current_query_index", 0)

    # Get recent sources (from last search)
    recent_sources = sources[-5:] if sources else []

    if not recent_sources:
        return {"current_phase": ResearchPhase.DECIDING}

    # Format sources for analysis
    sources_text = ""
    for i, source in enumerate(recent_sources, 1):
        content = source.get("content", "")[:1000]
        sources_text += f"\n[{i}] {source.get('title', '')}\nURL: {source.get('url', '')}\nContent: {content}...\n"

    # Get the query that was just executed
    last_query = ""
    if current_query_index > 0 and current_query_index <= len(planned_queries):
        last_query = planned_queries[current_query_index - 1].get("query", "")

    messages = [
        SystemMessage(content=ANALYZE_RESULTS_SYSTEM),
        HumanMessage(
            content=ANALYZE_RESULTS_USER.format(query=last_query, results=sources_text)
        ),
    ]

    response = await llm.ainvoke(messages)
    findings_data = _parse_json_response(response.content)

    new_findings: list[Finding] = []
    for f in findings_data:
        new_findings.append(
            Finding(
                summary=f["summary"],
                supporting_sources=f.get("supporting_sources", []),
                confidence=f.get("confidence", 0.5),
                topic_area=f.get("topic_area", "general"),
            )
        )

    return {
        "findings": new_findings,  # Will be accumulated via reducer
        "current_phase": ResearchPhase.DECIDING,
    }


async def decide_continuation_node(
    state: ResearchState,
) -> Command[Literal["execute_search", "plan_queries", "approval_findings", "synthesize"]]:
    """Decide whether to continue research or proceed to synthesis."""
    llm = get_llm()

    # Extract state with defaults
    current_iteration = state.get("current_iteration", 0)
    max_iterations = state.get("max_iterations", 7)
    review_mode = state.get("review_mode", ReviewMode.AUTONOMOUS)
    current_query_index = state.get("current_query_index", 0)
    planned_queries = state.get("planned_queries", [])
    findings = state.get("findings", [])
    sources = state.get("sources", [])
    topic = state.get("topic", "")

    # Check if we've hit max iterations
    if current_iteration >= max_iterations:
        if review_mode in [
            ReviewMode.REVIEW_BEFORE_WRITING,
            ReviewMode.REVIEW_AT_EACH_STAGE,
        ]:
            return Command(goto="approval_findings")
        return Command(goto="synthesize")

    # Check if there are more queries to execute
    if current_query_index < len(planned_queries):
        return Command(
            update={"current_iteration": current_iteration + 1},
            goto="execute_search",
        )

    # Ask LLM if we need more research
    findings_summary = "\n".join(
        [f"- {f.get('summary', '')}" for f in findings[-10:]]
    )
    sources_summary = "\n".join(
        [f"- {s.get('title', '')} ({s.get('url', '')})" for s in sources[-10:]]
    )

    messages = [
        SystemMessage(content=DECIDE_CONTINUATION_SYSTEM),
        HumanMessage(
            content=DECIDE_CONTINUATION_USER.format(
                topic=topic,
                findings_summary=findings_summary,
                sources_summary=sources_summary,
                num_findings=len(findings),
                num_sources=len(sources),
                current_iteration=current_iteration,
                max_iterations=max_iterations,
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    decision = _parse_json_response(response.content)

    should_continue = decision.get("should_continue", False)
    rationale = decision.get("rationale", "")
    gaps = decision.get("gaps_to_address", [])

    if should_continue and current_iteration < max_iterations:
        return Command(
            update={
                "should_continue_research": True,
                "continuation_rationale": ", ".join(gaps) if gaps else rationale,
                "current_iteration": current_iteration + 1,
            },
            goto="plan_queries",  # Generate new queries for gaps
        )

    # Research complete
    if review_mode in [
        ReviewMode.REVIEW_BEFORE_WRITING,
        ReviewMode.REVIEW_AT_EACH_STAGE,
    ]:
        return Command(
            update={"should_continue_research": False},
            goto="approval_findings",
        )

    return Command(
        update={"should_continue_research": False},
        goto="synthesize",
    )


async def approval_findings_node(
    state: ResearchState,
) -> Command[Literal["synthesize", "plan_queries", "handle_error"]]:
    """Pause for human approval of research findings."""
    findings = state.get("findings", [])
    sources = state.get("sources", [])

    approval = interrupt(
        {
            "type": "findings_approval",
            "findings": findings,
            "sources": sources,
            "num_findings": len(findings),
            "num_sources": len(sources),
            "message": "Please review the research findings before article generation.",
        }
    )

    if approval.get("approved"):
        return Command(goto="synthesize")
    elif approval.get("continue_research"):
        return Command(
            update={
                "current_iteration": 0,
                "continuation_rationale": approval.get("notes", ""),
            },
            goto="plan_queries",
        )
    else:
        return Command(
            update={"error_message": approval.get("reason", "Findings rejected")},
            goto="handle_error",
        )


# =============================================================================
# WRITING NODES
# =============================================================================


async def synthesize_node(state: ResearchState) -> dict:
    """Synthesize findings into an article outline."""
    llm = get_llm()

    findings = state.get("findings", [])
    topic = state.get("topic", "")

    findings_text = "\n".join(
        [
            f"- [{f.get('topic_area', 'general')}] {f.get('summary', '')} (confidence: {f.get('confidence', 0.5):.1f})"
            for f in findings
        ]
    )

    messages = [
        SystemMessage(content=SYNTHESIZE_SYSTEM),
        HumanMessage(
            content=SYNTHESIZE_USER.format(
                topic=topic,
                findings=findings_text,
            )
        ),
    ]

    response = await llm.ainvoke(messages)

    return {
        "article_outline": response.content,
        "current_phase": ResearchPhase.WRITING,
    }


async def write_article_node(state: ResearchState) -> dict:
    """Generate the article with human-like writing style."""
    llm = get_llm(temperature=0.8)  # Slightly higher for more natural writing

    findings = state.get("findings", [])
    sources = state.get("sources", [])
    topic = state.get("topic", "")
    article_outline = state.get("article_outline", "")

    # Format findings
    findings_text = "\n".join(
        [
            f"- {f.get('summary', '')} (Sources: {', '.join(f.get('supporting_sources', [])[:2])})"
            for f in findings
        ]
    )

    # Format sources
    sources_text = "\n".join(
        [f"- {s.get('title', '')}: {s.get('url', '')}" for s in sources[:15]]
    )

    messages = [
        SystemMessage(content=ARTICLE_WRITING_SYSTEM),
        HumanMessage(
            content=ARTICLE_WRITING_USER.format(
                topic=topic,
                outline=article_outline or "Create a logical structure",
                findings=findings_text,
                sources=sources_text,
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    article = response.content

    # Apply post-processing to enforce style
    article = _enforce_writing_style(article)

    return {
        "article": article,
        "current_phase": ResearchPhase.FACT_CHECKING,
    }


# =============================================================================
# GRAMMAR CHECK NODE
# =============================================================================


async def grammar_check_node(state: ResearchState) -> dict:
    """Check and fix grammar, spelling, and punctuation errors in the article."""
    llm = get_llm(temperature=0.1)  # Low temperature for consistent corrections

    # Extract state with .get() defaults (per skill guidelines)
    article = state.get("article", "")

    if not article:
        return {
            "grammar_corrections": [],
            "grammar_error_count": 0,
        }

    messages = [
        SystemMessage(content=GRAMMAR_CHECK_SYSTEM),
        HumanMessage(content=GRAMMAR_CHECK_USER.format(article=article)),
    ]

    response = await llm.ainvoke(messages)
    result = _parse_json_response(response.content)

    # Extract corrected article and apply style enforcement
    corrected_article = result.get("corrected_article", article)
    corrected_article = _enforce_writing_style(corrected_article)

    return {
        "article": corrected_article,
        "grammar_corrections": result.get("corrections", []),
        "grammar_error_count": result.get("error_count", 0),
    }


# =============================================================================
# FACT-CHECKING NODES
# =============================================================================


async def fact_check_node(
    state: ResearchState,
) -> Command[Literal["fix_claims", "grammar_check"]]:
    """Extract claims and verify them against sources."""
    llm = get_llm(temperature=0.1)  # Low temperature for consistent analysis

    article = state.get("article", "")
    findings = state.get("findings", [])
    sources = state.get("sources", [])
    fact_check_iteration = state.get("fact_check_iteration", 0)
    review_mode = state.get("review_mode", ReviewMode.AUTONOMOUS)

    # Extract claims from article
    extract_messages = [
        SystemMessage(content=EXTRACT_CLAIMS_SYSTEM),
        HumanMessage(content=EXTRACT_CLAIMS_USER.format(article=article)),
    ]

    extract_response = await llm.ainvoke(extract_messages)
    claims_data = _parse_json_response(extract_response.content)

    # Verify each claim
    findings_text = "\n".join([f"- {f.get('summary', '')}" for f in findings])
    sources_text = "\n".join(
        [f"- {s.get('title', '')}: {s.get('content', '')[:500]}" for s in sources[:10]]
    )

    # Get current date to help detect anachronistic dates
    current_date = datetime.now().strftime("%B %d, %Y")  # e.g., "January 02, 2026"

    results: list[FactCheckResult] = []
    for claim_item in claims_data:
        verify_messages = [
            SystemMessage(content=VERIFY_CLAIM_SYSTEM),
            HumanMessage(
                content=VERIFY_CLAIM_USER.format(
                    claim=claim_item["claim"],
                    current_date=current_date,
                    findings=findings_text,
                    sources=sources_text,
                )
            ),
        ]

        verify_response = await llm.ainvoke(verify_messages)
        verification = _parse_json_response(verify_response.content)

        results.append(
            FactCheckResult(
                claim=claim_item["claim"],
                sentence_index=claim_item.get("sentence_index", 0),
                is_verified=verification.get("is_verified", False),
                supporting_source=verification.get("supporting_source"),
                confidence=verification.get("confidence", 0.0),
                issue=verification.get("issue"),
            )
        )

    unverified = [r for r in results if not r["is_verified"]]

    # If there are unverified claims and we haven't hit max attempts
    if unverified and fact_check_iteration < 3:
        return Command(
            update={
                "fact_check_results": results,
                "unverified_claims": [u["claim"] for u in unverified],
                "fact_check_passed": False,
            },
            goto="fix_claims",
        )

    # All verified or max attempts reached
    return Command(
        update={
            "fact_check_results": results,
            "fact_check_passed": len(unverified) == 0,
            "current_phase": ResearchPhase.AWAITING_APPROVAL
            if review_mode == ReviewMode.REVIEW_AT_EACH_STAGE
            else ResearchPhase.COMPLETED,
        },
        goto="grammar_check",
    )


async def fix_claims_node(state: ResearchState) -> dict:
    """Rewrite article to fix unverified claims."""
    llm = get_llm(temperature=0.5)

    unverified_claims = state.get("unverified_claims", [])
    findings = state.get("findings", [])
    article = state.get("article", "")
    fact_check_iteration = state.get("fact_check_iteration", 0)

    # Format unverified claims
    unverified_text = "\n".join([f"- {claim}" for claim in unverified_claims])

    # Format verified findings
    findings_text = "\n".join([f"- {f.get('summary', '')}" for f in findings])

    messages = [
        SystemMessage(content=FIX_CLAIMS_SYSTEM),
        HumanMessage(
            content=FIX_CLAIMS_USER.format(
                article=article,
                unverified_claims=unverified_text,
                findings=findings_text,
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    fixed_article = response.content

    # Apply style enforcement again
    fixed_article = _enforce_writing_style(fixed_article)

    return {
        "article": fixed_article,
        "fact_check_iteration": fact_check_iteration + 1,
        "current_phase": ResearchPhase.FACT_CHECKING,
    }


async def approval_article_node(
    state: ResearchState,
) -> Command[Literal["complete", "write_article", "handle_error"]]:
    """Final approval for the generated article."""
    review_mode = state.get("review_mode", ReviewMode.AUTONOMOUS)
    fact_check_results = state.get("fact_check_results", [])
    article = state.get("article", "")
    sources = state.get("sources", [])
    article_outline = state.get("article_outline", "")

    if review_mode != ReviewMode.REVIEW_AT_EACH_STAGE:
        return Command(goto="complete")

    # Calculate verification score
    total_claims = len(fact_check_results)
    verified_claims = sum(1 for r in fact_check_results if r.get("is_verified", False))
    verification_score = verified_claims / total_claims if total_claims > 0 else 1.0

    approval = interrupt(
        {
            "type": "article_approval",
            "article": article,
            "fact_check_results": fact_check_results,
            "verification_score": verification_score,
            "sources": sources,
            "message": "Please review the final article.",
        }
    )

    if approval.get("approved"):
        return Command(goto="complete")
    elif approval.get("revise"):
        return Command(
            update={
                "article_outline": article_outline
                + f"\n\nRevision notes: {approval.get('notes', '')}",
            },
            goto="write_article",
        )
    else:
        return Command(
            update={"error_message": approval.get("reason", "Article rejected")},
            goto="handle_error",
        )


# =============================================================================
# TERMINAL NODES
# =============================================================================


async def complete_node(state: ResearchState) -> dict:
    """Mark research as completed successfully."""
    return {"current_phase": ResearchPhase.COMPLETED}


async def handle_error_node(state: ResearchState) -> dict:
    """Handle errors and failed states."""
    return {"current_phase": ResearchPhase.FAILED}
