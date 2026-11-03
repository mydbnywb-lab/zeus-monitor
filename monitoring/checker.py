import httpx
from config.settings import PANEL_URL


async def check_panel_connection():
    if not PANEL_URL:
        return {
            "online": False,
            "status": "not_configured",
            "message": "Panel URL is not configured",
        }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(PANEL_URL)

        return {
            "online": response.status_code < 500,
            "status": response.status_code,
            "message": "Panel is reachable",
        }

    except httpx.TimeoutException:
        return {
            "online": False,
            "status": "timeout",
            "message": "Panel connection timed out",
        }

    except httpx.RequestError:
        return {
            "online": False,
            "status": "connection_error",
            "message": "Unable to connect to panel",
        }
