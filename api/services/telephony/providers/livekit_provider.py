import uuid
from typing import Any, Dict, List, Optional

from api.services.livekit_service import LiveKitTokenService
from api.services.telephony.base import CallInitiationResult, TelephonyProvider


class LiveKitProvider(TelephonyProvider):
    PROVIDER_NAME = "livekit"
    WEBHOOK_ENDPOINT = "livekit"

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        room_name = kwargs.get("room_name")
        if not room_name:
            suffix = workflow_run_id or uuid.uuid4()
            room_name = f"dograh-room-{suffix}"

        service = LiveKitTokenService.from_values(
            api_key=self._config.get("api_key", ""),
            api_secret=self._config.get("api_secret", ""),
            url=self._config.get("url", ""),
        )

        token, identity = service.create_participant_token(
            room_name=room_name,
            identity=kwargs.get("identity"),
            participant_name=kwargs.get("participant_name"),
            metadata=kwargs.get("metadata"),
        )

        provider_metadata = {
            "room_name": room_name,
            "identity": identity,
            "token": token,
            "url": service.url,
        }

        return CallInitiationResult(
            call_id=room_name,
            status="ready",
            provider_metadata=provider_metadata,
            raw_response=provider_metadata,
        )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        return {"call_id": call_id, "status": "unknown"}

    async def get_available_phone_numbers(self) -> List[str]:
        return []

    def validate_config(self) -> bool:
        return bool(
            self._config.get("api_key")
            and self._config.get("api_secret")
            and self._config.get("url")
        )

    async def verify_webhook_signature(
        self, url: str, params: Dict[str, Any], signature: str
    ) -> bool:
        return False

    async def get_webhook_response(
        self, workflow_id: int, user_id: int, workflow_run_id: int
    ) -> str:
        return ""

    async def get_call_cost(self, call_id: str) -> Dict[str, Any]:
        return {
            "cost_usd": 0.0,
            "duration": 0,
            "status": "unknown",
            "raw_response": {},
        }

    def parse_status_callback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"call_id": data.get("call_id", ""), "status": "unknown", "extra": data}

    async def handle_websocket(
        self,
        websocket: "WebSocket",
        workflow_id: int,
        user_id: int,
        workflow_run_id: int,
    ) -> None:
        raise RuntimeError("LiveKit does not use telephony websocket handling")

    @classmethod
    def can_handle_webhook(
        cls, webhook_data: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return False

    @staticmethod
    def parse_inbound_webhook(webhook_data: Dict[str, Any]):
        raise RuntimeError("LiveKit does not parse inbound telephony webhooks")

    @staticmethod
    def validate_account_id(config_data: dict, webhook_account_id: str) -> bool:
        return False

    def normalize_phone_number(self, phone_number: str) -> str:
        return phone_number

    async def verify_inbound_signature(
        self, url: str, webhook_data: Dict[str, Any], signature: str
    ) -> bool:
        return False

    def generate_inbound_response(self, websocket_url: str) -> tuple:
        return "", "text/plain"

    @staticmethod
    def generate_error_response(error_type: str, message: str) -> tuple:
        return message, "text/plain"
