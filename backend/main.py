import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import PANEL_URL, PANEL_API_KEY, BOT_TOKEN
from database.db import init_db, close_db, AsyncSessionLocal
from database.models import MetricSnapshot, OutageHistory, AppSetting
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

            health_score = (
                round(online_nodes / len(node_list) * 100)
                if node_list else None
            )
            health_color = (
                "green" if health_score is not None and health_score >= 80
                else "yellow" if health_score is not None and health_score >= 50
                else "red" if health_score is not None
                else "unknown"
            )

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
            "health": {
                "score": health_score,
                "color": health_color,
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



DEFAULT_WELCOME_MESSAGE = (
    "⚡ <b>WELCOME TO ZEUS MONITOR</b>\n\n"
    "🟢 Monitoring system is ready.\n"
    "📊 Open your dashboard using the button below."
)


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



@app.get("/api/settings/panel")
async def get_panel_settings():
    from config import settings as cfg
    return {
        "panel_url": cfg.PANEL_URL,
        "check_interval": cfg.CHECK_INTERVAL,
        "api_key_configured": bool(cfg.PANEL_API_KEY),
    }


@app.put("/api/settings/panel")
async def save_panel_settings(payload: dict):
    from config import settings as cfg
    from pathlib import Path
    import os
    import re

    panel_url = payload.get("panel_url")
    interval = payload.get("check_interval")
    api_key = payload.get("api_key")

    if not isinstance(panel_url, str) or not panel_url.strip().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid panel URL")
    if not isinstance(interval, int) or interval < 10 or interval > 3600:
        raise HTTPException(status_code=400, detail="Interval must be between 10 and 3600 seconds")
    if api_key is not None and (not isinstance(api_key, str) or len(api_key) > 500):
        raise HTTPException(status_code=400, detail="Invalid API key")

    env_path = BASE_DIR / ".env"
    content = env_path.read_text() if env_path.exists() else ""

    updates = {
        "PANEL_URL": panel_url.strip().rstrip("/"),
        "CHECK_INTERVAL": str(interval),
    }
    if api_key:
        updates["PANEL_API_KEY"] = api_key.strip()

    for key, value in updates.items():
        line = f"{key}={value}"
        pattern = rf"(?m)^{re.escape(key)}=.*$"
        if re.search(pattern, content):
            content = re.sub(pattern, lambda _: line, content)
        else:
            content += ("\n" if content and not content.endswith("\n") else "") + line + "\n"

    env_path.write_text(content)
    os.chmod(env_path, 0o600)

    cfg.PANEL_URL = updates["PANEL_URL"]
    cfg.CHECK_INTERVAL = interval
    if api_key:
        cfg.PANEL_API_KEY = api_key.strip()

    import sys
    for module_name in (
        "backend.main",
        "monitoring.metrics",
        "monitoring.worker",
        "monitoring.checker",
        "monitoring.node_alerts",
        "monitoring.pasarguard",
    ):
        module = sys.modules.get(module_name)
        if module:
            if hasattr(module, "PANEL_URL"):
                module.PANEL_URL = cfg.PANEL_URL
            if hasattr(module, "PANEL_API_KEY"):
                module.PANEL_API_KEY = cfg.PANEL_API_KEY
            if hasattr(module, "CHECK_INTERVAL"):
                module.CHECK_INTERVAL = cfg.CHECK_INTERVAL

    return {"ok": True, "panel_url": cfg.PANEL_URL, "check_interval": cfg.CHECK_INTERVAL}



@app.get("/api/settings/public-alert")
async def get_public_alert_settings():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == "public_alert_chat")
        )
        setting = result.scalar_one_or_none()
        return {"chat": setting.value if setting else ""}


@app.put("/api/settings/public-alert")
async def save_public_alert_settings(payload: dict):
    import re
    from urllib.parse import urlparse

    chat = payload.get("chat", "")
    if not isinstance(chat, str) or len(chat) > 300:
        raise HTTPException(status_code=400, detail="Invalid destination")

    chat = chat.strip()
    if chat.startswith(("https://t.me/", "http://t.me/")):
        path = urlparse(chat).path.strip("/").split("/")
        if not path or path[0].startswith(("+", "joinchat")):
            raise HTTPException(
                status_code=400,
                detail="Private invite links are not supported; enter the numeric chat ID."
            )
        if path[0] == "c" and len(path) > 1 and path[1].isdigit():
            chat = "-100" + path[1]
        else:
            chat = "@" + path[0]

    if chat and not (
        re.fullmatch(r"@[A-Za-z0-9_]{5,}", chat)
        or re.fullmatch(r"-100\d+", chat)
    ):
        raise HTTPException(
            status_code=400,
            detail="Enter a public Telegram link, @username, or numeric channel/group ID."
        )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == "public_alert_chat")
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = chat
        else:
            db.add(AppSetting(key="public_alert_chat", value=chat))
        await db.commit()

    return {"ok": True, "configured": bool(chat)}



@app.post("/api/settings/public-alert/test")
async def test_public_alert():
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Bot token is not configured")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == "public_alert_chat")
        )
        setting = result.scalar_one_or_none()
        chat = setting.value if setting else ""

    if not chat:
        raise HTTPException(status_code=400, detail="ابتدا مقصد تلگرام را ذخیره کنید.")

    message = (
        "🧪✅ <b>پیام آزمایشی ZEUS MONITOR</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📡 اتصال ربات به مقصد اطلاع‌رسانی برقرار است.\n"
        "🔔 هشدارهای قطعی و بازیابی نود از این پس در این مقصد ارسال می‌شوند.\n"
        "🛡 <i>ZEUS MONITOR</i>"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat, "text": message, "parse_mode": "HTML"}
            )
            data = response.json()
        if not response.is_success or not data.get("ok"):
            detail = data.get("description", "ارسال پیام ناموفق بود.")
            raise HTTPException(status_code=400, detail=detail)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="ارتباط با تلگرام برقرار نشد.")

    return {"ok": True, "sent": True}


@app.get("/api/settings/welcome")
async def get_welcome_message():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSetting).where(AppSetting.key == "welcome_message")
        )
        setting = result.scalar_one_or_none()
    return {
        "message": setting.value if setting else DEFAULT_WELCOME_MESSAGE,
        "default_message": DEFAULT_WELCOME_MESSAGE,
    }


@app.put("/api/settings/welcome")
async def save_welcome_message(payload: dict):
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(message) > 3500:
        raise HTTPException(status_code=400, detail="Message is too long")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSetting).where(AppSetting.key == "welcome_message")
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = message
        else:
            session.add(AppSetting(key="welcome_message", value=message))
        await session.commit()

    return {"ok": True, "message": message}


@app.post("/api/settings/welcome/reset")
async def reset_welcome_message():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppSetting).where(AppSetting.key == "welcome_message")
        )
        setting = result.scalar_one_or_none()
        if setting:
            await session.delete(setting)
            await session.commit()
    return {"ok": True, "message": DEFAULT_WELCOME_MESSAGE}
