# mcp-calendar-server

An [MCP](https://modelcontextprotocol.io) server that exposes an existing **REST booking API** as typed,
annotated tools, so Claude, IDE assistants or your own agents can check, book and cancel appointments.

```
MCP client (Claude, agent) ──stdio/HTTP──► calendar_mcp.server ──httpx (auth, timeout, idempotency)──► booking REST API
```

## Integration patterns shown

| Concern | How |
|---|---|
| Typed tools | `free_slots(day)`, `book(day, start, customer)`, `cancel(booking_id)` with JSON schemas generated from type hints |
| Safety hints for clients | `readOnlyHint` / `destructiveHint` / `idempotentHint` tool annotations |
| Retries without duplicates | Deterministic `Idempotency-Key` per booking request |
| Input validation | Business-hour and ID formats checked before any upstream call |
| Error mapping | HTTP 409/404/5xx become clear tool errors for the model; upstream bodies are never leaked |
| Secrets | API token from environment, injected as `Authorization` header |
| Testing | In-memory MCP client against the server, upstream API via `httpx.ASGITransport` (no network) |

## Run

```bash
pip install -r requirements.txt
pytest -q
uvicorn calendar_mcp.fake_api:app --port 8001          # stand-in booking API
python -m calendar_mcp.server                          # MCP server on stdio
```

Claude Code: `claude mcp add calendar -- python -m calendar_mcp.server`
