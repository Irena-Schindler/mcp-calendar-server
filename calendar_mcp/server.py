"""MCP server exposing a REST booking API as typed, annotated tools for any MCP client (Claude, IDEs, agents)."""
from __future__ import annotations
import hashlib, os, re
from datetime import date
import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

API_URL = os.getenv("BOOKING_API_URL", "http://localhost:8001")
API_TOKEN = os.getenv("BOOKING_API_TOKEN", "dev-token")
TIME = re.compile(r"^(0[8-9]|1[0-6]):00$")

mcp = MCPServer("calendar", instructions="Check free slots before booking. Confirm details with the user first.")
_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=API_URL, timeout=10,
                                    headers={"Authorization": f"Bearer {API_TOKEN}"})
    return _client


def use_client(c: httpx.AsyncClient) -> None:
    """Dependency injection for tests."""
    global _client
    _client = c


def _check(r: httpx.Response) -> None:
    if r.status_code == 409:
        raise ToolError("That slot is no longer available. Call free_slots again.")
    if r.status_code == 404:
        raise ToolError("Booking not found.")
    if r.status_code >= 400:
        raise ToolError(f"Booking system error ({r.status_code}).")  # never leak upstream bodies


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def free_slots(day: date) -> list[str]:
    """Free one-hour slots (HH:MM) on a weekday."""
    r = await client().get(f"/slots/{day.isoformat()}")
    _check(r)
    return r.json()["free"]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def book(day: date, start: str, customer: str) -> dict:
    """Book a free slot. Retries with the same arguments never create duplicates."""
    if not TIME.match(start):
        raise ToolError("start must be a full hour between 08:00 and 16:00")
    if not 2 <= len(customer.strip()) <= 80:
        raise ToolError("customer name must be 2-80 characters")
    key = hashlib.sha256(f"{day}|{start}|{customer.strip().lower()}".encode()).hexdigest()[:24]
    r = await client().post("/bookings", json={"day": day.isoformat(), "start": start, "customer": customer.strip()},
                            headers={"Idempotency-Key": key})
    _check(r)
    return r.json()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def cancel(booking_id: str) -> str:
    """Cancel a booking by id (e.g. bk-3)."""
    if not re.fullmatch(r"bk-\d+", booking_id):
        raise ToolError("invalid booking id")
    _check(await client().delete(f"/bookings/{booking_id}"))
    return f"Cancelled {booking_id}."


if __name__ == "__main__":
    mcp.run()  # stdio transport; add to Claude Desktop / Claude Code as an MCP server
