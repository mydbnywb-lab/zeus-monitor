import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import PANEL_URL, PANEL_API_KEY
from database.db import init_db, close_db, AsyncSessionLocal
from database.models import MetricSnapshot, OutageHistory
from sqlalchemy import select
from monitoring.metrics import metrics_loop

BASE_DIR = Path(__file__).resolve().parent.parent
MINIAPP_DIR = BASE_DIR / "miniapp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    metrics_task = asyncio.create_task(metrics_loop())
    try:
        yield
    finally:
        metrics_task.cancel()
        try:
            await metrics_task
        except asyncio.CancelledError:
            pass
        await close_db()


app = FastAPI(
    title="ZEUS MONITOR",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/css", StaticFiles(directory=MINIAPP_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=MINIAPP_DIR / "js"), name="js")
app.mount("/assets", StaticFiles(directory=MINIAPP_DIR / "assets"), name="assets")


@app.get("/")
async def dashboard():
    return FileResponse(MINIAPP_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "zeus-backend"}


@app.get("/api/dashboard")
async def dashboard_data():
    try:
        async with httpx.AsyncClient(
            base_url=PANEL_URL.rstrip("/") + "/",
            headers={
                "X-Api-Key": PANEL_API_KEY,
                "Accept": "application/json",
            },
            timeout=20,
        ) as client:
            response = await client.get("api/system")
            response.raise_for_status()
            system = response.json()

            nodes_response = await client.get("api/nodes")
            nodes_response.raise_for_status()
            nodes_data = nodes_response.json()
            node_list = nodes_data.get("nodes", [])

            online_nodes = sum(
                1 for node in node_list
                if node.get("status") == "connected"
            )
            offline_nodes = len(node_list) - online_nodes

        return {
            "status": "online",
            "panel_version": system.get("version"),
            "users": {
                "total": system.get("total_user", 0),
                "active": system.get("active_users", 0),
                "online": system.get("online_users", 0),
                "on_hold": system.get("on_hold_users", 0),
                "expired": system.get("expired_users", 0),
                "disabled": system.get("disabled_users", 0),
                "limited": system.get("limited_users", 0),
            },
            "traffic": {
                "incoming": system.get("incoming_bandwidth", 0),
                "outgoing": system.get("outgoing_bandwidth", 0),
            },
            "resources": {
                "cpu": system.get("cpu_usage", 0),
                "memory_used": system.get("mem_used", 0),
                "memory_total": system.get("mem_total", 0),
                "disk_used": system.get("disk_used", 0),
                "disk_total": system.get("disk_total", 0),
                "uptime": system.get("uptime_seconds", 0),
            },
            "nodes": {
                "status": "online",
                "total": len(node_list),
                "online": online_nodes,
                "offline": offline_nodes,
                "items": [
                    {
                        "name": node.get("name", "Unknown Node"),
                        "status": node.get("status", "unknown"),
                        "traffic_bytes": (
                            int(node.get("uplink") or 0)
                            + int(node.get("downlink") or 0)
                        ),
                    }
                    for node in node_list
                ],
            },
        }

    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=502,
            detail=f"PasarGuard API returned HTTP {error.response.status_code}",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to PasarGuard",
        )

@app.get("/api/analytics")
async def analytics_data(range: str = "24h"):
    ranges = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }

    if range not in ranges:
        raise HTTPException(status_code=400, detail="Invalid range")

    since = datetime.now(timezone.utc) - ranges[range]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MetricSnapshot)
            .where(MetricSnapshot.recorded_at >= since)
            .order_by(MetricSnapshot.recorded_at.asc())
        )
        snapshots = result.scalars().all()

    return {
        "range": range,
        "count": len(snapshots),
        "samples": [
            {
                "time": item.recorded_at.isoformat(),
                "traffic": {
                    "incoming": item.incoming,
                    "outgoing": item.outgoing,
                },
                "users": {
                    "total": item.total_users,
                    "active": item.active_users,
                    "online": item.online_users,
                    "expired": item.expired_users,
                },
                "resources": {
                    "cpu": item.cpu,
                    "memory_used": item.memory_used,
                    "memory_total": item.memory_total,
                },
                "nodes": json.loads(item.nodes_json or "[]"),
            }
            for item in snapshots
        ],
    }



@app.get("/api/outages")
async def outage_history():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OutageHistory)
            .order_by(OutageHistory.started_at.desc())
            .limit(100)
        )
        records = result.scalars().all()

    return {
        "count": len(records),
        "items": [
            {
                "id": item.id,
                "service": item.service,
                "status": item.status,
                "started_at": item.started_at.isoformat(),
                "recovered_at": (
                    item.recovered_at.isoformat()
                    if item.recovered_at else None
                ),
                "duration_seconds": item.duration_seconds,
                "message": item.message,
            }
            for item in records
        ],
    }
