"""
Itniotech Voice API implementation of the TelephonyProvider interface.
"""

import hashlib
import hmac
import json
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import aiohttp
from loguru import logger

from api.enums import WorkflowRunMode
from api.services.telephony.base import (
    CallInitiationResult,
    NormalizedInboundData,
    TelephonyProvider,
)
from api.utils.tunnel import TunnelURLProvider

if TYPE_CHECKING:
    from fastapi import WebSocket


class ItniotechProvider(TelephonyProvider):
    """
    Itniotech implementation of TelephonyProvider.
    Uses API key/secret authentication and TwiML-compatible webhook responses.
    """

    PROVIDER_NAME = WorkflowRunMode.ITNIOTECH.value
    WEBHOOK_ENDPOINT = "twiml"

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ItniotechProvider with configuration.

        Args:
            config: Dictionary containing:
                - api_key: Itniotech API key
                - api_secret: Itniotech API secret
                - base_url: Optional API base URL override
                - from_numbers: List of phone numbers to use
        """
        self.api_key = config.get("api_key")
        self.api_secret = config.get("api_secret")
        self.base_url = config.get("base_url") or "https://www.itniotech.com/api/voice"
        self.from_numbers = config.get("from_numbers", [])

        if isinstance(self.from_numbers, str):
            self.from_numbers = [self.from_numbers]

    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authorization headers for Itniotech API."""
        return {
            "X-API-Key": self.api_key,
            "X-API-Secret": self.api_secret,
            "Content-Type": "application/json",
        }

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        """
        Initiate an outbound call via Itniotech Voice API.
        """
        if not self.validate_config():
            raise ValueError("Itniotech provider not properly configured")

        endpoint = f"{self.base_url.rstrip('/')}/calls"

        from_number = random.choice(self.from_numbers)
        logger.info(
            f"Selected phone number {from_number} for outbound call to {to_number}"
        )

        payload: Dict[str, Any] = {
            "to": to_number,
            "from": from_number,
            "webhook_url": webhook_url,
        }

        if workflow_run_id:
            backend_endpoint = await TunnelURLProvider.get_tunnel_url()
            callback_url = f"https://{backend_endpoint}/api/v1/telephony/itniotech/status-callback/{workflow_run_id}"
            payload["status_callback_url"] = callback_url

        payload.update(kwargs)

        headers = self._get_auth_headers()
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload, headers=headers) as response:
                response_text = await response.text()
                if response.status not in {200, 201}:
                    raise Exception(
                        f"Failed to initiate call via Itniotech (HTTP {response.status}): {response_text}"
                    )

                try:
                    response_data = await response.json()
                except Exception:
                    response_data = {"raw_response": response_text}

        call_id = (
            response_data.get("call_id")
            or response_data.get("id")
            or response_data.get("uuid")
        )

        if not call_id:
            raise Exception("No call identifier returned from Itniotech")

        return CallInitiationResult(
            call_id=call_id,
            status=response_data.get("status", "initiated"),
            provider_metadata={},
            raw_response=response_data,
        )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """
        Get the current status of an Itniotech call.
        """
        if not self.validate_config():
            raise ValueError("Itniotech provider not properly configured")

        endpoint = f"{self.base_url.rstrip('/')}/calls/{call_id}"
        headers = self._get_auth_headers()

        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, headers=headers) as response:
                if response.status != 200:
                    error_data = await response.text()
                    raise Exception(f"Failed to get call status: {error_data}")

                return await response.json()

    async def get_available_phone_numbers(self) -> List[str]:
        """
        Get list of available Itniotech phone numbers.
        """
        return self.from_numbers

    def validate_config(self) -> bool:
        """
        Validate Itniotech configuration.
        """
        return bool(self.api_key and self.api_secret and self.from_numbers)

    async def verify_webhook_signature(
        self, url: str, params: Dict[str, Any], signature: str
    ) -> bool:
        """
        Verify Itniotech webhook signature (HMAC SHA256 of URL + params).
        """
        if not self.api_secret or not signature:
            return False

        payload = f"{url}|{self._serialize_params(params)}"
        digest = hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(digest, signature)

    async def get_webhook_response(
        self, workflow_id: int, user_id: int, workflow_run_id: int
    ) -> str:
        """
        Generate TwiML response for starting a call session.
        """
        backend_endpoint = await TunnelURLProvider.get_tunnel_url()

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{backend_endpoint}/api/v1/telephony/ws/{workflow_id}/{user_id}/{workflow_run_id}"></Stream>
    </Connect>
    <Pause length="40"/>
</Response>"""

    async def get_call_cost(self, call_id: str) -> Dict[str, Any]:
        """
        Get cost information for a completed Itniotech call.
        """
        try:
            call_data = await self.get_call_status(call_id)
            cost_usd = float(
                call_data.get("cost_usd")
                or call_data.get("price")
                or call_data.get("cost")
                or 0.0
            )
            duration = int(
                call_data.get("duration")
                or call_data.get("billsec")
                or call_data.get("seconds")
                or 0
            )
            return {
                "cost_usd": cost_usd,
                "duration": duration,
                "status": call_data.get("status", "unknown"),
                "raw_response": call_data,
            }
        except Exception as e:
            logger.error(f"Exception fetching Itniotech call cost: {e}")
            return {"cost_usd": 0.0, "duration": 0, "status": "error", "error": str(e)}

    def parse_status_callback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Itniotech status callback data into generic format.
        """
        return {
            "call_id": data.get("call_id")
            or data.get("callId")
            or data.get("CallId")
            or data.get("uuid")
            or data.get("id", ""),
            "status": data.get("status") or data.get("CallStatus", ""),
            "from_number": data.get("from") or data.get("From"),
            "to_number": data.get("to") or data.get("To"),
            "direction": data.get("direction") or data.get("Direction"),
            "duration": data.get("duration") or data.get("Duration"),
            "extra": data,
        }

    async def handle_websocket(
        self,
        websocket: "WebSocket",
        workflow_id: int,
        user_id: int,
        workflow_run_id: int,
    ) -> None:
        """
        Handle Itniotech WebSocket connection.

        Accepts Twilio-style or Plivo-style start events.
        """
        from api.services.pipecat.run_pipeline import run_pipeline_itniotech

        try:
            first_msg = await websocket.receive_text()
            first_payload = json.loads(first_msg)
            logger.debug(
                f"Itniotech WebSocket first message for run {workflow_run_id}: {first_payload}"
            )

            if first_payload.get("event") == "connected":
                start_msg = await websocket.receive_text()
                start_payload = json.loads(start_msg)
            else:
                start_payload = first_payload

            if start_payload.get("event") != "start":
                logger.error(
                    f"Expected 'start' event, got: {start_payload.get('event')}"
                )
                await websocket.close(code=4400, reason="Expected start event")
                return

            start_data = start_payload.get("start", {})
            stream_sid = (
                start_data.get("streamSid")
                or start_data.get("streamId")
                or start_data.get("stream_id")
            )
            call_sid = (
                start_data.get("callSid")
                or start_data.get("callId")
                or start_data.get("call_id")
            )

            if not stream_sid or not call_sid:
                logger.error(f"Missing stream or call identifiers: {start_data}")
                await websocket.close(code=4400, reason="Missing stream identifiers")
                return

            await run_pipeline_itniotech(
                websocket, stream_sid, call_sid, workflow_id, workflow_run_id, user_id
            )
        except Exception as e:
            logger.error(f"Error in Itniotech WebSocket handler: {e}")
            raise

    # ======== INBOUND CALL METHODS ========

    @classmethod
    def can_handle_webhook(
        cls, webhook_data: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        """
        Determine if this provider can handle the incoming webhook.
        """
        user_agent = headers.get("user-agent", "").lower()
        provider_hint = str(webhook_data.get("provider", "")).lower()
        return (
            "itniotech" in user_agent
            or "itniotech" in provider_hint
            or "itniotech" in str(webhook_data).lower()
        )

    @staticmethod
    def parse_inbound_webhook(webhook_data: Dict[str, Any]) -> NormalizedInboundData:
        """
        Parse Itniotech-specific inbound webhook data into normalized format.
        """
        return NormalizedInboundData(
            provider=ItniotechProvider.PROVIDER_NAME,
            call_id=webhook_data.get("call_id")
            or webhook_data.get("callId")
            or webhook_data.get("uuid", ""),
            from_number=ItniotechProvider.normalize_phone_number(
                webhook_data.get("from", "") or webhook_data.get("From", "")
            ),
            to_number=ItniotechProvider.normalize_phone_number(
                webhook_data.get("to", "") or webhook_data.get("To", "")
            ),
            direction=webhook_data.get("direction", ""),
            call_status=webhook_data.get("status", ""),
            account_id=webhook_data.get("account_id")
            or webhook_data.get("accountId"),
            from_country=webhook_data.get("from_country"),
            to_country=webhook_data.get("to_country"),
            raw_data=webhook_data,
        )

    @staticmethod
    def validate_account_id(config_data: dict, webhook_account_id: str) -> bool:
        """
        Validate Itniotech account identifier from webhook matches configuration.
        """
        if not webhook_account_id:
            return True

        stored_account_id = config_data.get("api_key")
        return stored_account_id == webhook_account_id

    @staticmethod
    def normalize_phone_number(phone_number: str) -> str:
        """
        Normalize a phone number to E.164 format.
        """
        if not phone_number:
            return ""

        clean_number = phone_number.replace(" ", "").replace("-", "")
        if clean_number.startswith("+"):
            return clean_number
        if clean_number.startswith("1") and len(clean_number) == 11:
            return f"+{clean_number}"
        if len(clean_number) == 10:
            return f"+1{clean_number}"
        return f"+{clean_number}"

    async def verify_inbound_signature(
        self, url: str, webhook_data: Dict[str, Any], signature: str
    ) -> bool:
        """
        Verify the signature of an inbound Itniotech webhook.
        """
        return await self.verify_webhook_signature(url, webhook_data, signature)

    @staticmethod
    async def generate_inbound_response(
        websocket_url: str, workflow_run_id: int = None
    ) -> tuple:
        """
        Generate TwiML response for an inbound Itniotech webhook.
        """
        from fastapi import Response

        status_callback_attr = ""
        if workflow_run_id:
            backend_endpoint = await TunnelURLProvider.get_tunnel_url()
            status_callback_url = f"https://{backend_endpoint}/api/v1/telephony/itniotech/status-callback/{workflow_run_id}"
            status_callback_attr = f' statusCallback="{status_callback_url}"'

        twiml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}"{status_callback_attr}></Stream>
    </Connect>
    <Pause length="40"/>
</Response>"""

        return Response(content=twiml_content, media_type="application/xml")

    @staticmethod
    def generate_error_response(error_type: str, message: str) -> tuple:
        """
        Generate a TwiML error response for Itniotech.
        """
        from fastapi import Response

        twiml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Sorry, there was an error processing your call. {message}</Say>
    <Hangup/>
</Response>"""

        return Response(content=twiml_content, media_type="application/xml")

    @staticmethod
    def generate_validation_error_response(error_type) -> tuple:
        """
        Generate error response for validation failures with organizational debugging info.
        """
        from fastapi import Response

        from api.errors.telephony_errors import TELEPHONY_ERROR_MESSAGES, TelephonyError

        message = TELEPHONY_ERROR_MESSAGES.get(
            error_type, TELEPHONY_ERROR_MESSAGES[TelephonyError.GENERAL_AUTH_FAILED]
        )

        twiml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Sorry, there was an error validating your call. {message}</Say>
    <Hangup/>
</Response>"""

        return Response(content=twiml_content, media_type="application/xml")

    @staticmethod
    def _serialize_params(params: Dict[str, Any]) -> str:
        """Serialize params into a sorted query string for signature verification."""
        return "&".join(f"{key}={params[key]}" for key in sorted(params.keys()))
