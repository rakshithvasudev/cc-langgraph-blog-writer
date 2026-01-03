"""Research domain models."""

from typing import Optional, TypedDict


class Source(TypedDict):
    """A source from web search."""

    url: str
    title: str
    content: str
    score: float
    retrieved_at: str


class Finding(TypedDict):
    """A research finding extracted from sources."""

    summary: str
    supporting_sources: list[str]  # List of source URLs
    confidence: float
    topic_area: str


class SearchQuery(TypedDict):
    """A planned search query."""

    query: str
    rationale: str
    executed: bool


class FactCheckResult(TypedDict):
    """Result of fact-checking a single claim."""

    claim: str
    sentence_index: int
    is_verified: bool
    supporting_source: Optional[str]
    confidence: float
    issue: Optional[str]
