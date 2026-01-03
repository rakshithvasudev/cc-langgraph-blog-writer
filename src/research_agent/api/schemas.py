"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..models.enums import ReviewMode


class ResearchRequest(BaseModel):
    """Request to start a new research task."""

    topic: str = Field(..., description="The research topic", min_length=3, max_length=500)
    review_mode: ReviewMode = Field(
        default=ReviewMode.AUTONOMOUS,
        description="Level of human oversight required",
    )
    max_iterations: int = Field(
        default=7,
        ge=5,
        le=15,
        description="Maximum research iterations (5-15)",
    )


class ResearchStatus(BaseModel):
    """Current status of a research task."""

    thread_id: str
    topic: str
    phase: str
    iteration: int
    max_iterations: int
    sources_count: int
    findings_count: int
    is_awaiting_approval: bool
    pending_approval_type: Optional[str] = None
    error_message: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request to approve/reject a pending stage."""

    approved: bool = Field(..., description="Whether to approve this stage")
    modified_data: Optional[dict] = Field(
        default=None,
        description="Optional modifications (e.g., modified queries)",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for rejection (if not approved)",
    )
    continue_research: bool = Field(
        default=False,
        description="For findings rejection: whether to continue researching",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes (e.g., revision notes for article)",
    )


class PendingApproval(BaseModel):
    """Details of a pending approval request."""

    thread_id: str
    type: str
    message: str
    data: dict


class SourceResponse(BaseModel):
    """A source in the response."""

    url: str
    title: str
    score: float


class FindingResponse(BaseModel):
    """A finding in the response."""

    summary: str
    topic_area: str
    confidence: float
    supporting_sources: list[str]


class FactCheckResultResponse(BaseModel):
    """A fact-check result in the response."""

    claim: str
    is_verified: bool
    supporting_source: Optional[str]
    confidence: float
    issue: Optional[str]


class ResearchResult(BaseModel):
    """Final research result."""

    thread_id: str
    topic: str
    article: str
    sources: list[SourceResponse]
    findings: list[FindingResponse]
    fact_check_report: list[FactCheckResultResponse]
    verification_score: float
    completed_at: datetime


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    thread_id: Optional[str] = None
