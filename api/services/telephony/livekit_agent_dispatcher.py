from loguru import logger

from api.db import db_client


async def dispatch_livekit_agent(payload) -> None:
    """Handle LiveKit agent dispatch payloads for the built-in agent service."""
    logger.info(
        "LiveKit dispatch received: room={room} run={run} workflow={workflow} user={user}",
        room=payload.room_name,
        run=payload.workflow_run_id,
        workflow=payload.workflow_id,
        user=payload.user_id,
    )

    if payload.workflow_run_id:
        try:
            workflow_run = await db_client.get_workflow_run_by_id(
                payload.workflow_run_id
            )
        except Exception as exc:
            logger.warning(
                "Failed to load workflow run {run_id} for LiveKit dispatch: {error}",
                run_id=payload.workflow_run_id,
                error=exc,
            )
            return

        if workflow_run:
            await db_client.update_workflow_run(
                payload.workflow_run_id,
                gathered_context={
                    **(workflow_run.gathered_context or {}),
                    "livekit_room_name": payload.room_name,
                    "livekit_agent_identity": payload.agent_identity,
                    "livekit_server_url": payload.server_url,
                },
            )
