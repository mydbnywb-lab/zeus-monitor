import asyncio
import logging

from config.settings import CHECK_INTERVAL, PANEL_URL
from monitoring.checker import check_panel_connection
from monitoring.outages import record_status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("ZEUS")


async def monitor_loop():
    if not PANEL_URL:
        logger.error("PANEL_URL is not configured.")
        return

    logger.info("ZEUS monitoring worker started.")

    while True:
        try:
            result = await check_panel_connection()

            event = await record_status(
                service="pasarguard_panel",
                online=result["online"],
                message=result["message"],
            )

            logger.info(
                "Panel status: %s | Event: %s",
                result["status"],
                event["event"],
            )

        except Exception:
            logger.exception("Monitoring check failed.")

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(monitor_loop())
    except KeyboardInterrupt:
        logger.info("ZEUS monitoring worker stopped.")
