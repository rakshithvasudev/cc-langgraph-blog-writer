---
name: run-server
description: Start the LangGraph research agent development server
user_invocable: true
---

# Run Server

Start the LangGraph development server for the research agent.

## Instructions

Run the following command to start the server:

```bash
cd /home/rajathdb/research_agent && langgraph dev
```

## Server URLs

Once running, access:

| Service | URL |
|---------|-----|
| API | http://127.0.0.1:2024 |
| Studio UI | https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024 |
| API Docs | http://127.0.0.1:2024/docs |

## Quick Test

To test with a new research topic in Studio:

1. Open the Studio UI link above
2. Create a **new thread** (important!)
3. Submit input:

```json
{
  "topic": "Your research topic",
  "review_mode": "autonomous",
  "max_iterations": 5
}
```

## Stop Server

Press `Ctrl+C` in the terminal to stop the server.
