"""FastAPI application entry point for the research agent."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config.settings import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if not settings.debug else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Create FastAPI app
app = FastAPI(
    title="Research Agent API",
    description="LangGraph-based research agent that performs extensive web research and generates human-quality articles",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Research Agent API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "start_research": "POST /research/start",
            "get_status": "GET /research/{thread_id}/status",
            "get_pending_approval": "GET /research/{thread_id}/pending-approval",
            "approve_stage": "POST /research/{thread_id}/approve",
            "get_result": "GET /research/{thread_id}/result",
            "cancel_research": "DELETE /research/{thread_id}",
            "list_tasks": "GET /research/",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    logger.info(
        "starting_research_agent",
        host=settings.api_host,
        port=settings.api_port,
        debug=settings.debug,
        llm_provider=settings.llm_provider,
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    logger.info("shutting_down_research_agent")


def run():
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "research_agent.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
