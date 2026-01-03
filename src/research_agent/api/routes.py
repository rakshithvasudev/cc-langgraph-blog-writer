"""FastAPI route definitions for the research agent."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from langgraph.types import Command

from ..graph.state import get_initial_state
from ..models.enums import ResearchPhase
from .dependencies import (
    delete_thread_metadata,
    get_graph,
    get_thread_metadata,
    get_thread_store,
    save_thread_metadata,
)
from .schemas import (
    ApprovalRequest,
    ErrorResponse,
    FactCheckResultResponse,
    FindingResponse,
    PendingApproval,
    ResearchRequest,
    ResearchResult,
    ResearchStatus,
    SourceResponse,
)

router = APIRouter(prefix="/research", tags=["research"])


# =============================================================================
# Background task helpers
# =============================================================================


async def run_research_until_interrupt(graph, initial_state: dict, config: dict) -> None:
    """Run the graph until it completes or hits an interrupt."""
    try:
        async for _event in graph.astream(initial_state, config, stream_mode="updates"):
            # Events are processed, state is updated via checkpointer
            pass
    except Exception as e:
        # Log error but don't crash - state is persisted
        import structlog

        logger = structlog.get_logger()
        logger.error("research_error", error=str(e), thread_id=config["configurable"]["thread_id"])


async def resume_research(graph, config: dict, resume_data: dict) -> None:
    """Resume graph execution after approval."""
    try:
        async for _event in graph.astream(
            Command(resume=resume_data),
            config,
            stream_mode="updates",
        ):
            pass
    except Exception as e:
        import structlog

        logger = structlog.get_logger()
        logger.error("resume_error", error=str(e), thread_id=config["configurable"]["thread_id"])


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("/start", response_model=ResearchStatus)
async def start_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    graph=Depends(get_graph),
):
    """
    Start a new research task.

    Returns immediately with a thread_id for tracking.
    Research runs in background until completion or interrupt.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Create initial state
    initial_state = get_initial_state(
        topic=request.topic,
        review_mode=request.review_mode,
        max_iterations=request.max_iterations,
    )

    # Store thread metadata
    await save_thread_metadata(
        thread_id,
        {
            "topic": request.topic,
            "review_mode": request.review_mode.value,
            "max_iterations": request.max_iterations,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Start research in background
    background_tasks.add_task(run_research_until_interrupt, graph, initial_state, config)

    return ResearchStatus(
        thread_id=thread_id,
        topic=request.topic,
        phase=ResearchPhase.PLANNING.value,
        iteration=0,
        max_iterations=request.max_iterations,
        sources_count=0,
        findings_count=0,
        is_awaiting_approval=False,
    )


@router.get("/{thread_id}/status", response_model=ResearchStatus)
async def get_research_status(
    thread_id: str,
    graph=Depends(get_graph),
):
    """Get the current status of a research task."""
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = graph.get_state(config)
        if state.values is None:
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

        values = state.values

        # Check if there's a pending interrupt
        is_awaiting = bool(state.tasks) and any(
            hasattr(task, "interrupts") and task.interrupts for task in state.tasks
        )
        pending_type = None
        if is_awaiting:
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    pending_type = task.interrupts[0].value.get("type")
                    break

        return ResearchStatus(
            thread_id=thread_id,
            topic=values.get("topic", ""),
            phase=values.get("current_phase", ResearchPhase.PLANNING).value
            if hasattr(values.get("current_phase", ResearchPhase.PLANNING), "value")
            else str(values.get("current_phase", "planning")),
            iteration=values.get("current_iteration", 0),
            max_iterations=values.get("max_iterations", 7),
            sources_count=len(values.get("sources", [])),
            findings_count=len(values.get("findings", [])),
            is_awaiting_approval=is_awaiting,
            pending_approval_type=pending_type,
            error_message=values.get("error_message"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}") from e


@router.get("/{thread_id}/pending-approval", response_model=PendingApproval)
async def get_pending_approval(
    thread_id: str,
    graph=Depends(get_graph),
):
    """
    Get details of pending approval request.

    Returns the data that needs human review.
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = graph.get_state(config)

        # Find interrupt data
        interrupt_data = None
        if state.tasks:
            for task in state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    interrupt_data = task.interrupts[0].value
                    break

        if not interrupt_data:
            raise HTTPException(status_code=404, detail="No pending approval")

        return PendingApproval(
            thread_id=thread_id,
            type=interrupt_data.get("type", "unknown"),
            message=interrupt_data.get("message", ""),
            data=interrupt_data,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}") from e


@router.post("/{thread_id}/approve", response_model=ResearchStatus)
async def approve_stage(
    thread_id: str,
    approval: ApprovalRequest,
    background_tasks: BackgroundTasks,
    graph=Depends(get_graph),
):
    """
    Approve or reject a pending stage.

    Resumes the graph execution with the approval decision.
    """
    config = {"configurable": {"thread_id": thread_id}}

    # Build resume payload
    resume_data = {
        "approved": approval.approved,
        "reason": approval.reason,
        "continue_research": approval.continue_research,
        "notes": approval.notes,
    }

    if approval.modified_data:
        resume_data["modified_queries"] = approval.modified_data.get("queries")

    # Resume graph execution in background
    background_tasks.add_task(resume_research, graph, config, resume_data)

    # Return current status (will update as graph progresses)
    return await get_research_status(thread_id, graph)


@router.get("/{thread_id}/result", response_model=ResearchResult)
async def get_research_result(
    thread_id: str,
    graph=Depends(get_graph),
):
    """
    Get the final research result.

    Only available when research is complete.
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = graph.get_state(config)
        if state.values is None:
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

        values = state.values

        current_phase = values.get("current_phase")
        phase_value = current_phase.value if hasattr(current_phase, "value") else str(current_phase)

        if phase_value != ResearchPhase.COMPLETED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Research not complete. Current phase: {phase_value}",
            )

        # Calculate verification score
        fact_check_results = values.get("fact_check_results", [])
        total_claims = len(fact_check_results)
        verified_claims = sum(1 for r in fact_check_results if r.get("is_verified", False))
        verification_score = verified_claims / total_claims if total_claims > 0 else 1.0

        return ResearchResult(
            thread_id=thread_id,
            topic=values["topic"],
            article=values.get("article", ""),
            sources=[
                SourceResponse(
                    url=s["url"],
                    title=s["title"],
                    score=s.get("score", 0.0),
                )
                for s in values.get("sources", [])
            ],
            findings=[
                FindingResponse(
                    summary=f["summary"],
                    topic_area=f.get("topic_area", "general"),
                    confidence=f.get("confidence", 0.5),
                    supporting_sources=f.get("supporting_sources", []),
                )
                for f in values.get("findings", [])
            ],
            fact_check_report=[
                FactCheckResultResponse(
                    claim=r["claim"],
                    is_verified=r.get("is_verified", False),
                    supporting_source=r.get("supporting_source"),
                    confidence=r.get("confidence", 0.0),
                    issue=r.get("issue"),
                )
                for r in fact_check_results
            ],
            verification_score=verification_score,
            completed_at=datetime.now(timezone.utc),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving result: {e!s}") from e


@router.delete("/{thread_id}", response_model=dict)
async def cancel_research(
    thread_id: str,
    _thread_store=Depends(get_thread_store),
):
    """Cancel an ongoing research task."""
    await delete_thread_metadata(thread_id)
    return {"status": "cancelled", "thread_id": thread_id}


@router.get("/", response_model=list[dict])
async def list_research_tasks(
    _thread_store=Depends(get_thread_store),
):
    """List all research tasks."""
    tasks = []
    for thread_id, metadata in _thread_store.items():
        tasks.append(
            {
                "thread_id": thread_id,
                "topic": metadata.get("topic", ""),
                "review_mode": metadata.get("review_mode", ""),
                "started_at": metadata.get("started_at", ""),
            }
        )
    return tasks
