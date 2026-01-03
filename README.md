# Research Agent

A LangGraph-based research agent that performs extensive web research using Tavily and generates human-quality articles with fact-checking.

## Features

- **Extensive Web Research**: Uses Tavily for comprehensive web searches
- **Configurable Depth**: 5-15 research iterations (default: 7)
- **Human-in-the-Loop**: Three review modes for different oversight levels
- **Human Writing Style**: No em dashes, avoids AI patterns
- **Fact-Checking**: Verifies all claims against research sources

## Quick Start

```bash
# Install dependencies
pip install -e .

# Copy and edit environment variables
cp .env.example .env
# Add your ANTHROPIC_API_KEY and TAVILY_API_KEY

# Run with LangGraph CLI
pip install "langgraph-cli[inmem]"
langgraph dev
```

## API Endpoints

- `POST /research/start` - Start research with topic, review_mode, max_iterations
- `GET /research/{id}/status` - Check current status
- `POST /research/{id}/approve` - Approve pending stages
- `GET /research/{id}/result` - Get final article

## Review Modes

- `autonomous` - Runs to completion without human intervention
- `review_before_writing` - Pauses after research for approval
- `review_at_each_stage` - Pauses at queries, findings, and article
