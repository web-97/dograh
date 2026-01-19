import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

import jwt

from api.constants import LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL


@dataclass(frozen=True)
class LiveKitTokenConfig:
    api_key: str
    api_secret: str
    url: str


class LiveKitTokenService:
    def __init__(self, config: LiveKitTokenConfig) -> None:
        self._config = config

    @classmethod
    def from_env(cls) -> "LiveKitTokenService":
        if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET or not LIVEKIT_URL:
            raise ValueError("LiveKit environment variables are not configured")
        config = LiveKitTokenConfig(
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            url=LIVEKIT_URL,
        )
        return cls(config)

    @classmethod
    def from_values(cls, api_key: str, api_secret: str, url: str) -> "LiveKitTokenService":
        if not api_key or not api_secret or not url:
            raise ValueError("LiveKit configuration values are missing")
        config = LiveKitTokenConfig(api_key=api_key, api_secret=api_secret, url=url)
        return cls(config)

    def create_participant_token(
        self,
        room_name: str,
        identity: Optional[str] = None,
        participant_name: Optional[str] = None,
        metadata: Optional[str] = None,
        ttl_seconds: int = 3600,
    ) -> tuple[str, str]:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")

        identity_value = identity or f"participant-{uuid.uuid4()}"
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)

        payload = {
            "iss": self._config.api_key,
            "sub": identity_value,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "name": participant_name or identity_value,
            "metadata": metadata,
            "video": {
                "room": room_name,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": True,
            },
        }

        token = jwt.encode(payload, self._config.api_secret, algorithm="HS256")
        return token, identity_value

    @property
    def url(self) -> str:
        return self._config.url

    @property
    def api_key(self) -> str:
        return self._config.api_key

    @property
    def api_secret(self) -> str:
        return self._config.api_secret
