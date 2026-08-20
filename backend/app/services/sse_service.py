"""Server-Sent Events (SSE) broadcaster and real-time streaming service."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator


class EventPublisher:
    """Pub/Sub broker managing connected SSE client streams."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Register a new client queue and yield SSE-formatted messages."""
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(q)
        try:
            # Yield initial ping event
            init_event = self._format_sse(
                "connection", {"status": "connected", "time": datetime.utcnow().isoformat()}
            )
            yield init_event

            while True:
                msg = await q.get()
                yield msg
        finally:
            self._subscribers.discard(q)

    def publish(self, event_type: str, data: Any) -> None:
        """Broadcast an event payload to all active client queues."""
        msg = self._format_sse(event_type, data)
        for q in list(self._subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    @staticmethod
    def _format_sse(event_type: str, data: Any) -> str:
        payload = json.dumps(data, default=str)
        return f"event: {event_type}\ndata: {payload}\n\n"


# Global singleton instance
event_publisher = EventPublisher()
