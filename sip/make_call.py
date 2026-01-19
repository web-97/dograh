import asyncio
import os
from dotenv import load_dotenv
from livekit import api

load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
SIP_OUTBOUND_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")

async def main():
    lk = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )

    room_name = "dograh-test-room"
    phone_number = "+628123456789"  # 你的被叫，E.164

    p = await lk.sip.create_sip_participant(
        api.CreateSIPParticipantRequest(
            room_name=room_name,
            sip_trunk_id=SIP_OUTBOUND_TRUNK_ID,
            sip_call_to=phone_number,
            participant_identity="phone_user",
            participant_name="Phone User",
            wait_until_answered=False,
        )
    )

    print("SIP participant created:", p)
    await lk.aclose()

if __name__ == "__main__":
    asyncio.run(main())
