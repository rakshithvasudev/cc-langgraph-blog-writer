"""Tavily search service wrapper."""

from datetime import datetime, timezone
from typing import Optional

from tavily import AsyncTavilyClient

from ..config.settings import settings
from ..models.research import Source


class TavilySearchService:
    """Wrapper for Tavily search API using async client."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the async Tavily client."""
        self.api_key = api_key or settings.tavily_api_key
        self.client = AsyncTavilyClient(api_key=self.api_key)
        self.search_depth = settings.tavily_search_depth
        self.max_results = settings.tavily_max_results

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: Optional[str] = None,
    ) -> list[Source]:
        """
        Execute a search query and return formatted sources.

        Args:
            query: The search query
            max_results: Override default max results
            search_depth: Override default search depth ("basic" or "advanced")

        Returns:
            List of Source objects with search results
        """
        results = await self.client.search(
            query=query,
            search_depth=search_depth or self.search_depth,
            max_results=max_results or self.max_results,
            include_raw_content=True,
        )

        sources: list[Source] = []
        retrieved_at = datetime.now(timezone.utc).isoformat()

        for result in results.get("results", []):
            sources.append(
                Source(
                    url=result.get("url", ""),
                    title=result.get("title", ""),
                    content=result.get("content", ""),
                    score=result.get("score", 0.0),
                    retrieved_at=retrieved_at,
                )
            )

        return sources

    async def search_with_context(
        self,
        query: str,
        context: str,
        max_results: Optional[int] = None,
    ) -> list[Source]:
        """
        Execute a contextual search for more relevant results.

        Args:
            query: The search query
            context: Additional context to improve search relevance
            max_results: Override default max results

        Returns:
            List of Source objects with search results
        """
        # Combine query with context for better results
        enhanced_query = f"{query} {context}"
        return await self.search(enhanced_query, max_results=max_results)


# Singleton instance
_search_service: Optional[TavilySearchService] = None


def get_search_service() -> TavilySearchService:
    """Get or create the singleton search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = TavilySearchService()
    return _search_service
