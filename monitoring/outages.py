from datetime import datetime, timezone

from sqlalchemy import select

from database.db import AsyncSessionLocal
from database.models import OutageHistory


async def record_status(service: str, online: bool, message: str = ""):
    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(OutageHistory)
            .where(
                OutageHistory.service == service,
                OutageHistory.recovered_at.is_(None)
            )
            .order_by(OutageHistory.id.desc())
        )

        outage = result.scalars().first()

        now = datetime.now(timezone.utc)

        if not online:
            if outage is None:
                outage = OutageHistory(
                    service=service,
                    status="down",
                    started_at=now,
                    message=message,
                )

                session.add(outage)
                await session.commit()

                return {
                    "event": "outage_started",
                    "service": service,
                }

            outage.message = message
            await session.commit()

            return {
                "event": "still_down",
                "service": service,
            }

        if outage is not None:
            started_at = outage.started_at

            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)

            outage.status = "recovered"
            outage.recovered_at = now
            outage.duration_seconds = int(
                (now - started_at).total_seconds()
            )

            await session.commit()

            return {
                "event": "outage_recovered",
                "service": service,
                "duration_seconds": outage.duration_seconds,
            }

        return {
            "event": "online",
            "service": service,
        }
