"""Minimal dependency-free application boundary for M0."""


def health_payload() -> dict[str, str]:
    """Return the service health representation used by the future API."""
    return {"status": "ok", "service": "prophecy-backend"}
