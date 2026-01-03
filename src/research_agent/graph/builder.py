"""StateGraph construction for the research agent."""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    analyze_results_node,
    approval_article_node,
    approval_findings_node,
    approval_queries_node,
    complete_node,
    decide_continuation_node,
    execute_search_node,
    fact_check_node,
    fix_claims_node,
    grammar_check_node,
    handle_error_node,
    plan_queries_node,
    synthesize_node,
    write_article_node,
)
from .state import ResearchState


def build_research_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> StateGraph:
    """
    Build the research agent StateGraph.

    Graph Flow:
    START -> plan_queries -> approval_queries -> execute_search ->
    analyze_results -> decide_continuation -> [loop or continue] ->
    approval_findings -> synthesize -> write_article ->
    fact_check -> [fix_claims loop] -> grammar_check -> approval_article ->
    complete -> END

    Args:
        checkpointer: Optional checkpointer for state persistence.
                     Defaults to in-memory if not provided.

    Returns:
        Compiled StateGraph ready for execution.
    """
    builder = StateGraph(ResearchState)

    # ==========================================================================
    # Add all nodes
    # ==========================================================================

    # Research phase nodes
    builder.add_node("plan_queries", plan_queries_node)
    builder.add_node("approval_queries", approval_queries_node)
    builder.add_node("execute_search", execute_search_node)
    builder.add_node("analyze_results", analyze_results_node)
    builder.add_node("decide_continuation", decide_continuation_node)
    builder.add_node("approval_findings", approval_findings_node)

    # Writing phase nodes
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("write_article", write_article_node)
    builder.add_node("grammar_check", grammar_check_node)

    # Fact-checking phase nodes
    builder.add_node("fact_check", fact_check_node)
    builder.add_node("fix_claims", fix_claims_node)
    builder.add_node("approval_article", approval_article_node)

    # Terminal nodes
    builder.add_node("complete", complete_node)
    builder.add_node("handle_error", handle_error_node)

    # ==========================================================================
    # Define edges
    # ==========================================================================

    # Entry point
    builder.add_edge(START, "plan_queries")

    # Research flow
    builder.add_edge("plan_queries", "approval_queries")
    # approval_queries uses Command for routing to execute_search or handle_error

    builder.add_edge("execute_search", "analyze_results")
    builder.add_edge("analyze_results", "decide_continuation")
    # decide_continuation uses Command for routing:
    #   - execute_search (more queries to run)
    #   - plan_queries (need new queries)
    #   - approval_findings (review mode requires approval)
    #   - synthesize (proceed to writing)

    # approval_findings uses Command for routing to synthesize, plan_queries, or handle_error

    # Writing flow
    builder.add_edge("synthesize", "write_article")
    builder.add_edge("write_article", "fact_check")
    # fact_check uses Command to route to fix_claims or grammar_check
    builder.add_edge("grammar_check", "approval_article")

    # Fact-checking flow
    # fact_check uses Command for routing to fix_claims or grammar_check
    builder.add_edge("fix_claims", "fact_check")  # Loop back for re-verification

    # approval_article uses Command for routing to complete, write_article, or handle_error

    # Terminal edges
    builder.add_edge("complete", END)
    builder.add_edge("handle_error", END)

    # ==========================================================================
    # Compile with checkpointer
    # ==========================================================================

    if checkpointer is None:
        checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


def get_memory_checkpointer() -> MemorySaver:
    """Get an in-memory checkpointer for development."""
    return MemorySaver()


def get_postgres_checkpointer(connection_string: str) -> BaseCheckpointSaver:
    """
    Get a PostgreSQL checkpointer for production.

    Args:
        connection_string: PostgreSQL connection string

    Returns:
        PostgreSQL-backed checkpointer
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    checkpointer = PostgresSaver.from_conn_string(connection_string)
    checkpointer.setup()  # Create tables if needed
    return checkpointer


# =============================================================================
# Module-level graph export for LangGraph CLI
# =============================================================================
# The LangGraph CLI expects a compiled graph at module level.
# This is used by `langgraph dev` and `langgraph up` commands.
# IMPORTANT: Do NOT include a checkpointer - LangGraph CLI handles persistence.

def _build_graph_for_cli() -> StateGraph:
    """Build graph without checkpointer for LangGraph CLI."""
    builder = StateGraph(ResearchState)

    # ==========================================================================
    # Add all nodes
    # ==========================================================================

    # Research phase nodes
    builder.add_node("plan_queries", plan_queries_node)
    builder.add_node("approval_queries", approval_queries_node)
    builder.add_node("execute_search", execute_search_node)
    builder.add_node("analyze_results", analyze_results_node)
    builder.add_node("decide_continuation", decide_continuation_node)
    builder.add_node("approval_findings", approval_findings_node)

    # Writing phase nodes
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("write_article", write_article_node)
    builder.add_node("grammar_check", grammar_check_node)

    # Fact-checking phase nodes
    builder.add_node("fact_check", fact_check_node)
    builder.add_node("fix_claims", fix_claims_node)
    builder.add_node("approval_article", approval_article_node)

    # Terminal nodes
    builder.add_node("complete", complete_node)
    builder.add_node("handle_error", handle_error_node)

    # ==========================================================================
    # Define edges
    # ==========================================================================
    # IMPORTANT: Only define edges that are ALWAYS taken.
    # Nodes that use Command for routing handle their own destinations.
    # Multiple edges from a single node = PARALLEL execution (wrong!)
    # Command with goto = CONDITIONAL routing (correct!)

    # Entry point
    builder.add_edge(START, "plan_queries")

    # plan_queries -> approval_queries (always)
    builder.add_edge("plan_queries", "approval_queries")

    # approval_queries uses Command to route to execute_search or handle_error
    # NO static edge here - Command handles it

    # execute_search -> analyze_results (always)
    builder.add_edge("execute_search", "analyze_results")

    # analyze_results -> decide_continuation (always)
    builder.add_edge("analyze_results", "decide_continuation")

    # decide_continuation uses Command to route dynamically
    # NO static edge here - Command handles it

    # approval_findings uses Command to route dynamically
    # NO static edge here - Command handles it

    # synthesize -> write_article (always)
    builder.add_edge("synthesize", "write_article")

    # write_article -> fact_check (always)
    builder.add_edge("write_article", "fact_check")

    # fact_check uses Command to route to fix_claims or grammar_check
    # NO static edge here - Command handles it

    # grammar_check -> approval_article (always)
    builder.add_edge("grammar_check", "approval_article")

    # fix_claims -> fact_check (always loops back)
    builder.add_edge("fix_claims", "fact_check")

    # approval_article uses Command to route dynamically
    # NO static edge here - Command handles it

    # Terminal edges
    builder.add_edge("complete", END)
    builder.add_edge("handle_error", END)

    # Compile WITHOUT checkpointer - CLI provides its own
    return builder.compile()


graph = _build_graph_for_cli()
