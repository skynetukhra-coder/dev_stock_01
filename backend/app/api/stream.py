"""Server-Sent Events (SSE) streaming endpoint."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..services.sse_service import event_publisher

router = APIRouter(prefix="/stream", tags=["Streaming"])


@router.get("/events")
async def stream_events() -> StreamingResponse:
    """Stream live market events, signals, and risk updates via Server-Sent Events."""
    return StreamingResponse(
        event_publisher.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
