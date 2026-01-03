"""FastAPI dependencies for dependency injection."""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

from ..config.settings import settings
from ..graph.builder import build_research_graph, get_postgres_checkpointer

# Global instances (initialized on startup)
_graph: Optional[StateGraph] = None
_checkpointer: Optional[BaseCheckpointSaver] = None
_thread_store: dict[str, dict] = {}  # Simple in-memory store for thread metadata


def get_checkpointer() -> BaseCheckpointSaver:
    """Get or create the checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        if settings.use_postgres and settings.postgres_uri:
            _checkpointer = get_postgres_checkpointer(settings.postgres_uri)
        else:
            _checkpointer = MemorySaver()
    return _checkpointer


def get_graph() -> StateGraph:
    """Get or create the compiled graph instance."""
    global _graph
    if _graph is None:
        checkpointer = get_checkpointer()
        _graph = build_research_graph(checkpointer=checkpointer)
    return _graph


def get_thread_store() -> dict[str, dict]:
    """Get the thread metadata store."""
    return _thread_store


async def save_thread_metadata(thread_id: str, metadata: dict) -> None:
    """Save metadata for a thread."""
    _thread_store[thread_id] = metadata


async def get_thread_metadata(thread_id: str) -> Optional[dict]:
    """Get metadata for a thread."""
    return _thread_store.get(thread_id)


async def delete_thread_metadata(thread_id: str) -> None:
    """Delete metadata for a thread."""
    if thread_id in _thread_store:
        del _thread_store[thread_id]


def reset_graph() -> None:
    """Reset the graph instance (useful for testing)."""
    global _graph, _checkpointer
    _graph = None
    _checkpointer = None
