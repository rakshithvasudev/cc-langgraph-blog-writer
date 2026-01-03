"""Research agent state schema with LangGraph reducers."""

from operator import add
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from ..models.enums import ResearchPhase, ReviewMode
from ..models.research import FactCheckResult, Finding, SearchQuery, Source


class ResearchState(TypedDict):
    """
    Complete state for the research agent graph.

    Uses Annotated types with reducers to properly accumulate
    list-based fields across node executions.
    """

    # Configuration (set at start, not modified)
    topic: str
    review_mode: ReviewMode
    max_iterations: int

    # Research progress tracking
    current_iteration: int
    current_phase: ResearchPhase

    # Query planning and execution
    planned_queries: list[SearchQuery]
    current_query_index: int

    # Accumulated research data (using add reducer)
    sources: Annotated[list[Source], add]
    findings: Annotated[list[Finding], add]

    # Messages for LLM context
    messages: Annotated[list[AnyMessage], add_messages]

    # Decision tracking
    should_continue_research: bool
    continuation_rationale: str

    # Human-in-the-loop state
    pending_approval_type: Optional[str]  # "queries", "findings", "article"
    approval_payload: Optional[dict]

    # Article synthesis
    article_outline: Optional[str]
    article: Optional[str]

    # Grammar check state
    grammar_corrections: list[str]
    grammar_error_count: int

    # Fact-checking state
    fact_check_results: list[FactCheckResult]
    unverified_claims: list[str]
    fact_check_passed: bool
    fact_check_iteration: int

    # Error handling
    error_message: Optional[str]


def get_initial_state(
    topic: str,
    review_mode: ReviewMode = ReviewMode.AUTONOMOUS,
    max_iterations: int = 7,
) -> ResearchState:
    """Create the initial state for a new research task."""
    return ResearchState(
        topic=topic,
        review_mode=review_mode,
        max_iterations=max_iterations,
        current_iteration=0,
        current_phase=ResearchPhase.PLANNING,
        planned_queries=[],
        current_query_index=0,
        sources=[],
        findings=[],
        messages=[],
        should_continue_research=True,
        continuation_rationale="",
        pending_approval_type=None,
        approval_payload=None,
        article_outline=None,
        article=None,
        grammar_corrections=[],
        grammar_error_count=0,
        fact_check_results=[],
        unverified_claims=[],
        fact_check_passed=False,
        fact_check_iteration=0,
        error_message=None,
    )
