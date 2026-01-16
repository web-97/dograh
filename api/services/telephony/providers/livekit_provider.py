"""
LiveKit SIP implementation of the TelephonyProvider interface.
"""

import random
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import aiohttp
import jwt
from fastapi import Response
from loguru import logger

from api.enums import WorkflowRunMode
from api.services.telephony.base import (
    CallInitiationResult,
    NormalizedInboundData,
    TelephonyProvider,
)

if TYPE_CHECKING:
    from fastapi import WebSocket


class LiveKitProvider(TelephonyProvider):
    """
    LiveKit SIP implementation of TelephonyProvider.
    Uses the LiveKit SIP API to create outbound SIP participants.
    """

    PROVIDER_NAME = WorkflowRunMode.LIVEKIT.value
    WEBHOOK_ENDPOINT = "livekit"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LiveKitProvider with configuration.

        Args:
            config: Dictionary containing:
                - server_url: LiveKit server URL (https://your-livekit.example)
                - api_key: LiveKit API key
                - api_secret: LiveKit API secret
                - sip_trunk_id: LiveKit SIP trunk ID
                - from_numbers: Optional list of caller IDs
                - room_prefix: Optional room name prefix
        """
        self.server_url = config.get("server_url")
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.sip_trunk_id = config.get("sip_trunk_id")
        self.from_numbers = config.get("from_numbers", [])
        self.room_prefix = config.get("room_prefix", "dograh-call")

        if isinstance(self.from_numbers, str):
            self.from_numbers = [self.from_numbers]

    def _create_api_token(self) -> str:
        if not self.api_key or not self.api_secret:
            raise ValueError("LiveKit API key/secret not configured")

        now = int(time.time())
        payload = {
            "iss": self.api_key,
            "iat": now,
            "nbf": now - 10,
            "exp": now + 3600,
        }
        return jwt.encode(payload, self.api_secret, algorithm="HS256")

    def _get_headers(self) -> Dict[str, str]:
        token = self._create_api_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _build_room_name(self, workflow_run_id: Optional[int]) -> str:
        suffix = workflow_run_id or uuid.uuid4().hex[:12]
        return f"{self.room_prefix}-{suffix}"

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        """
        Initiate an outbound call via LiveKit SIP.
        """
        if not self.validate_config():
            raise ValueError("LiveKit provider not properly configured")

        endpoint = f"{self.server_url.rstrip('/')}/twirp/livekit.SIP/CreateSIPParticipant"
        room_name = self._build_room_name(workflow_run_id)
        participant_identity = f"pstn-{workflow_run_id or uuid.uuid4().hex[:12]}"

        payload: Dict[str, Any] = {
            "sip_trunk_id": self.sip_trunk_id,
            "sip_call_to": to_number,
            "room_name": room_name,
            "participant_identity": participant_identity,
            "participant_name": "Phone Call",
            "metadata": {
                "workflow_run_id": str(workflow_run_id) if workflow_run_id else "",
                "webhook_url": webhook_url,
            },
        }

        if self.from_numbers:
            payload["sip_call_from"] = random.choice(self.from_numbers)

        payload.update(kwargs)

        headers = self._get_headers()

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                if response.status not in {200, 201}:
                    error_text = await response.text()
                    raise Exception(
                        f"Failed to initiate LiveKit SIP call: {response.status} {error_text}"
                    )

                response_data = await response.json()

        call_id = (
            response_data.get("sip_call_id")
            or response_data.get("call_id")
            or response_data.get("participant_id")
            or room_name
        )

        return CallInitiationResult(
            call_id=call_id,
            status="started",
            provider_metadata={"room_name": room_name},
            raw_response=response_data,
        )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """
        LiveKit SIP does not provide a lightweight call status API in this flow.
        """
        return {"call_id": call_id, "status": "unknown"}

    async def get_available_phone_numbers(self) -> List[str]:
        return self.from_numbers

    def validate_config(self) -> bool:
        return bool(self.server_url and self.api_key and self.api_secret and self.sip_trunk_id)

    async def verify_webhook_signature(
        self, url: str, params: Dict[str, Any], signature: str
    ) -> bool:
        logger.warning("LiveKit webhooks are not configured for signature verification")
        return False

    async def get_webhook_response(
        self, workflow_id: int, user_id: int, workflow_run_id: int
    ) -> str:
        return ""

    async def get_call_cost(self, call_id: str) -> Dict[str, Any]:
        return {"cost_usd": 0.0, "duration": 0, "status": "unknown"}

    def parse_status_callback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "call_id": data.get("sip_call_id") or data.get("call_id", ""),
            "status": data.get("status", ""),
            "from_number": data.get("sip_call_from"),
            "to_number": data.get("sip_call_to"),
            "direction": data.get("direction"),
            "duration": data.get("duration"),
            "extra": data,
        }

    async def handle_websocket(
        self,
        websocket: "WebSocket",
        workflow_id: int,
        user_id: int,
        workflow_run_id: int,
    ) -> None:
        await websocket.close(code=4400, reason="LiveKit does not use this websocket")

    @classmethod
    def can_handle_webhook(
        cls, webhook_data: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        return False

    @staticmethod
    def parse_inbound_webhook(webhook_data: Dict[str, Any]) -> NormalizedInboundData:
        return NormalizedInboundData(
            provider=LiveKitProvider.PROVIDER_NAME,
            call_id=webhook_data.get("sip_call_id", ""),
            from_number=LiveKitProvider.normalize_phone_number(
                webhook_data.get("sip_call_from", "")
            ),
            to_number=LiveKitProvider.normalize_phone_number(
                webhook_data.get("sip_call_to", "")
            ),
            direction=webhook_data.get("direction", ""),
            call_status=webhook_data.get("status", ""),
            raw_data=webhook_data,
        )

    @staticmethod
    def validate_account_id(config_data: dict, webhook_account_id: str) -> bool:
        return config_data.get("api_key") == webhook_account_id

    @staticmethod
    def normalize_phone_number(phone_number: str) -> str:
        if not phone_number:
            return ""
        if phone_number.startswith("+"):
            return phone_number
        return f"+{phone_number}"

    async def verify_inbound_signature(
        self, url: str, webhook_data: Dict[str, Any], signature: str
    ) -> bool:
        return False

    @staticmethod
    def generate_inbound_response(websocket_url: str, workflow_run_id: int = None) -> tuple:
        message = "LiveKit SIP inbound handling is not configured."
        return Response(content=message, media_type="text/plain")

    @staticmethod
    def generate_error_response(error_type: str, message: str) -> tuple:
        return Response(content=message, media_type="text/plain")

    @staticmethod
    def generate_validation_error_response(error_type) -> tuple:
        return Response(content=str(error_type), media_type="text/plain")
