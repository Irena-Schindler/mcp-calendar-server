"""Stand-in for an existing booking system's REST API (what you typically have to integrate)."""
from datetime import date
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="booking-api")
HOURS = [f"{h:02d}:00" for h in range(8, 17)]
_bookings: dict[str, dict] = {}


class BookingIn(BaseModel):
    day: date
    start: str
    customer: str


def _auth(token: str | None) -> None:
    if token != "Bearer dev-token":
        raise HTTPException(401, "unauthorized")


@app.get("/slots/{day}")
def slots(day: date, authorization: str | None = Header(None)) -> dict:
    _auth(authorization)
    taken = {b["start"] for b in _bookings.values() if b["day"] == day.isoformat()}
    return {"day": day.isoformat(), "free": [h for h in HOURS if h not in taken] if day.weekday() < 5 else []}


@app.post("/bookings", status_code=201)
def create(b: BookingIn, authorization: str | None = Header(None),
           idempotency_key: str | None = Header(None)) -> dict:
    _auth(authorization)
    if idempotency_key and idempotency_key in _bookings:
        return _bookings[idempotency_key]
    if b.start not in slots(b.day, authorization)["free"]:
        raise HTTPException(409, "slot not available")
    rec = {"id": f"bk-{len(_bookings) + 1}", "day": b.day.isoformat(), "start": b.start, "customer": b.customer}
    _bookings[idempotency_key or rec["id"]] = rec
    return rec


@app.delete("/bookings/{booking_id}", status_code=204)
def cancel(booking_id: str, authorization: str | None = Header(None)) -> None:
    _auth(authorization)
    key = next((k for k, v in _bookings.items() if v["id"] == booking_id), None)
    if key is None:
        raise HTTPException(404, "not found")
    del _bookings[key]
