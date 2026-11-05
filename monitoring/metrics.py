import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from config.settings import CHECK_INTERVAL, PANEL_URL, PANEL_API_KEY
from database.db import AsyncSessionLocal
from database.models import MetricSnapshot
from monitoring.outages import record_status

logger = logging.getLogger("ZEUS.METRICS")


async def collect_metrics():
    async with httpx.AsyncClient(
        base_url=PANEL_URL.rstrip("/") + "/",
        headers={
            "X-Api-Key": PANEL_API_KEY,
            "Accept": "application/json",
        },
        timeout=20,
    ) as client:
        system_response = await client.get("api/system")
        system_response.raise_for_status()
        system = system_response.json()

        nodes_response = await client.get("api/nodes")
        nodes_response.raise_for_status()
        nodes = nodes_response.json().get("nodes", [])

    safe_nodes = [
        {
            "name": node.get("name", "Unknown Node"),
            "status": node.get("status", "unknown"),
            "traffic_bytes": (
                int(node.get("uplink") or 0)
                + int(node.get("downlink") or 0)
            ),
        }
        for node in nodes
    ]

    for node in nodes:
        name = str(node.get("name") or "Unknown Node")
        status = str(node.get("status") or "").strip().lower()

        if status in {"connected", "online", "running"}:
            await record_status(f"node:{name}", True, status)
        elif status in {"disconnected", "offline", "stopped"}:
            await record_status(f"node:{name}", False, status)

    snapshot = MetricSnapshot(
        recorded_at=datetime.now(timezone.utc),
        incoming=float(system.get("incoming_bandwidth") or 0),
        outgoing=float(system.get("outgoing_bandwidth") or 0),
        total_users=int(system.get("total_user") or 0),
        active_users=int(system.get("active_users") or 0),
        online_users=int(system.get("online_users") or 0),
        expired_users=int(system.get("expired_users") or 0),
        cpu=float(system.get("cpu_usage") or 0),
        memory_used=float(system.get("mem_used") or 0),
        memory_total=float(system.get("mem_total") or 0),
        nodes_json=json.dumps(safe_nodes, ensure_ascii=False),
    )

    async with AsyncSessionLocal() as session:
        session.add(snapshot)
        await session.commit()


async def metrics_loop():
    logger.info("ZEUS metrics collector started.")

    while True:
        try:
            await collect_metrics()
            logger.info("Metrics snapshot saved.")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Metrics collection failed.")

        await asyncio.sleep(max(10, CHECK_INTERVAL))
