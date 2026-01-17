from typing import Optional

from pydantic import BaseModel, Field


class LiveKitSessionRequest(BaseModel):
    """Request payload for creating a LiveKit session/token."""

    room_name: Optional[str] = Field(
        default=None, description="Existing room name to join."
    )
    identity: Optional[str] = Field(
        default=None, description="Participant identity (defaults to UUID)."
    )
    participant_name: Optional[str] = Field(
        default=None, description="Human-readable participant name."
    )
    metadata: Optional[str] = Field(
        default=None, description="Optional metadata string for the participant."
    )
    ttl_seconds: int = Field(
        default=3600, ge=300, le=24 * 60 * 60, description="Token TTL in seconds."
    )


class LiveKitSessionResponse(BaseModel):
    """Response payload for LiveKit session/token creation."""

    room_name: str
    identity: str
    token: str
    url: str
