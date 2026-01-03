"""Enums for the research agent."""

from enum import Enum


class ReviewMode(str, Enum):
    """Review mode determines when human approval is required."""

    AUTONOMOUS = "autonomous"
    REVIEW_BEFORE_WRITING = "review_before_writing"
    REVIEW_AT_EACH_STAGE = "review_at_each_stage"


class ResearchPhase(str, Enum):
    """Current phase of the research process."""

    PLANNING = "planning"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    DECIDING = "deciding"
    SYNTHESIZING = "synthesizing"
    WRITING = "writing"
    FACT_CHECKING = "fact_checking"
    FIXING_CLAIMS = "fixing_claims"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
