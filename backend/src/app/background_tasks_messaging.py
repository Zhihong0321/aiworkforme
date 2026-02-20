"""
MODULE: Application Background Tasks - Unified Messaging
PURPOSE: Outbound queue polling/dispatch loop for canonical messaging tables.
"""
import asyncio
import logging
import os

from sqlmodel import Session

from src.infra.database import engine
from routers.messaging import (
    dispatch_next_outbound_for_tenant,
    list_tenant_ids_with_queued_outbound,
)

logger = logging.getLogger(__name__)


OUTBOUND_POLL_SECONDS = float(os.getenv("MESSAGING_OUTBOUND_POLL_SECONDS", "2"))
OUTBOUND_BATCH_PER_TENANT = int(os.getenv("MESSAGING_OUTBOUND_BATCH_PER_TENANT", "5"))


async def background_outbound_dispatch_loop():
    """
    Polls due queued outbound rows and dispatches them in small tenant-scoped batches.
    """
    logger.info(
        "Starting unified outbound dispatch loop (poll=%ss, batch_per_tenant=%s)",
        OUTBOUND_POLL_SECONDS,
        OUTBOUND_BATCH_PER_TENANT,
    )
    while True:
        processed_count = 0
        try:
            with Session(engine) as session:
                tenant_ids = list_tenant_ids_with_queued_outbound(session)

                for tenant_id in tenant_ids:
                    for _ in range(OUTBOUND_BATCH_PER_TENANT):
                        result = dispatch_next_outbound_for_tenant(session, tenant_id)
                        if not result:
                            break
                        processed_count += 1
        except Exception as exc:
            logger.exception("Unified outbound loop error: %s", exc)

        if processed_count == 0:
            await asyncio.sleep(OUTBOUND_POLL_SECONDS)
        else:
            await asyncio.sleep(0)
