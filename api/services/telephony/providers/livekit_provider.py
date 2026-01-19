import uuid
from typing import Any, Dict, List, Optional

from api.enums import WorkflowRunMode
from api.services.livekit_service import LiveKitTokenService
from api.services.telephony.base import CallInitiationResult, TelephonyProvider
from livekit import api as livekit_api
from livekit.protocol.sip import CreateSIPParticipantRequest

class LiveKitProvider(TelephonyProvider):
    PROVIDER_NAME = WorkflowRunMode.LIVEKIT.value
    WEBHOOK_ENDPOINT = None

    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config

    @staticmethod
    def _get_api_url(url: str) -> str:
        if url.startswith("wss://"):
            return "https://" + url[len("wss://") :]
        if url.startswith("ws://"):
            return "http://" + url[len("ws://") :]
        return url

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        # 生成/复用 LiveKit 房间名
        room_name = kwargs.get("room_name")
        if not room_name:
            suffix = workflow_run_id or uuid.uuid4()
            room_name = f"dograh-room-{suffix}"

        # 使用组织级 LiveKit 配置生成 agent token
        service = LiveKitTokenService.from_values(
            api_key=self._config.get("api_key", ""),
            api_secret=self._config.get("api_secret", ""),
            url=self._config.get("url", ""),
        )

        # agent 与 caller 使用不同身份与显示名，避免同名参与者
        agent_identity = kwargs.get("identity") or f"agent-{workflow_run_id or uuid.uuid4()}"
        agent_name = kwargs.get("participant_name") or "Agent"
        token, identity = service.create_participant_token(
            room_name=room_name,
            identity=agent_identity,
            participant_name=agent_name,
            metadata=kwargs.get("metadata"),
        )

        # SIP 呼出依赖 LiveKit SIP Trunk
        sip_trunk_id = self._config.get("sip_trunk_id")
        sip_call_to = self._config.get("sip_call_to")

        if not sip_trunk_id:
            raise ValueError("livekit_sip_trunk_id_required")

        # 呼叫方的独立身份与显示名
        caller_identity = f"caller-{workflow_run_id or uuid.uuid4()}"
        caller_name = kwargs.get("caller_name") or "Caller"
        participant_metadata = kwargs.get("participant_metadata")


        # 创建 SIP 参与者并等待接听完成后再继续
        sip_request = CreateSIPParticipantRequest(
            sip_trunk_id=sip_trunk_id,
            sip_call_to=to_number.replace("+62","885562"),
            room_name=room_name,
            participant_identity=caller_identity,
            participant_name=caller_name,
            participant_metadata=participant_metadata or "",
            wait_until_answered=False,
        )
        if sip_call_to:
            sip_request.sip_call_to = sip_call_to

        # LiveKit API 需要 HTTP(S) URL（从 ws/wss 转换）
        api_url = self._get_api_url(service.url)
        async with livekit_api.LiveKitAPI(
            url=api_url,
            api_key=service.api_key,
            api_secret=service.api_secret,
        ) as lkapi:
            sip_participant = await lkapi.sip.create_sip_participant(sip_request)

        # 返回用于前端/日志的 LiveKit 会话信息
        provider_metadata = {
            "room_name": room_name,
            "identity": identity,
            "token": token,
            "url": service.url,
            "sip_trunk_id": sip_trunk_id,
            "sip_call_to": sip_call_to,
            "sip_participant_id": sip_participant.participant_id,
            "sip_participant_identity": sip_participant.participant_identity,
            "sip_call_id": sip_participant.sip_call_id,
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
            and self._config.get("sip_trunk_id")
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
