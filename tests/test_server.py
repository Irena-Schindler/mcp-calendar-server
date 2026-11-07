import asyncio, json
from datetime import date, timedelta
import httpx
import mcp
import pytest
from calendar_mcp import fake_api, server


def weekday() -> str:
    d = date.today() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


@pytest.fixture(autouse=True)
def wired():
    fake_api._bookings.clear()
    server.use_client(httpx.AsyncClient(transport=httpx.ASGITransport(app=fake_api.app),
                                        base_url="http://api", headers={"Authorization": "Bearer dev-token"}))
    yield


def call(name, args):
    async def go():
        async with mcp.Client(server.mcp) as c:
            return await c.call_tool(name, args)
    return asyncio.run(go())


def test_tools_are_listed_with_safety_annotations():
    async def go():
        async with mcp.Client(server.mcp) as c:
            return {t.name: t.annotations for t in (await c.list_tools()).tools}
    tools = asyncio.run(go())
    assert tools["free_slots"].read_only_hint and tools["cancel"].destructive_hint


def test_book_then_slot_disappears():
    day = weekday()
    assert not call("book", {"day": day, "start": "09:00", "customer": "Max Muster"}).is_error
    free = call("free_slots", {"day": day}).structured_content["result"]
    assert "09:00" not in free and "10:00" in free


def test_retry_is_idempotent():
    day = weekday()
    a = json.loads(call("book", {"day": day, "start": "11:00", "customer": "Eva"}).content[0].text)
    b = json.loads(call("book", {"day": day, "start": "11:00", "customer": "eva "}).content[0].text)
    assert a["id"] == b["id"] and len(fake_api._bookings) == 1


def test_conflict_and_validation_return_tool_errors():
    day = weekday()
    call("book", {"day": day, "start": "12:00", "customer": "Max"})
    r = call("book", {"day": day, "start": "12:00", "customer": "Someone Else"})
    assert r.is_error and "no longer available" in r.content[0].text
    assert call("book", {"day": day, "start": "07:30", "customer": "Max"}).is_error
    assert call("cancel", {"booking_id": "DROP TABLE"}).is_error
