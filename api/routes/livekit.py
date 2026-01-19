import uuid

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.db import db_client
from api.db.models import UserModel
from api.enums import OrganizationConfigurationKey
from api.schemas.livekit import LiveKitSessionRequest, LiveKitSessionResponse
from api.services.auth.depends import get_user
from api.services.livekit_service import LiveKitTokenService

router = APIRouter(prefix="/livekit", tags=["livekit"])


@router.post("/session", response_model=LiveKitSessionResponse)
async def create_livekit_session(
    payload: LiveKitSessionRequest,
    user: UserModel = Depends(get_user),
) -> LiveKitSessionResponse:
    """Create a LiveKit access token for a participant in a room."""
    try:
        if user.selected_organization_id:
            config = await db_client.get_configuration(
                user.selected_organization_id,
                OrganizationConfigurationKey.TELEPHONY_CONFIGURATION.value,
            )
        else:
            config = None

        if config and config.value and config.value.get("provider") == "livekit":
            service = LiveKitTokenService.from_values(
                api_key=config.value.get("api_key", ""),
                api_secret=config.value.get("api_secret", ""),
                url=config.value.get("url", ""),
            )
    except ValueError as exc:
        logger.error(f"LiveKit config error: {exc}")
        raise HTTPException(status_code=500, detail="livekit_not_configured") from exc

    room_name = payload.room_name or f"dograh-room-{uuid.uuid4()}"

    token, identity = service.create_participant_token(
        room_name=room_name,
        identity=payload.identity or f"user-{user.id}",
        participant_name=payload.participant_name or user.provider_id,
        metadata=payload.metadata,
        ttl_seconds=payload.ttl_seconds,
    )

    return LiveKitSessionResponse(
        room_name=room_name,
        identity=identity,
        token=token,
        url=service.url,
    )
