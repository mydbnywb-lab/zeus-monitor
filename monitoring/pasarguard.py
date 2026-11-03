import httpx

from config.settings import PANEL_URL, PANEL_API_KEY


class PasarGuardClient:
    def __init__(self):
        if not PANEL_URL:
            raise ValueError("PANEL_URL is not configured")

        if not PANEL_API_KEY:
            raise ValueError("PANEL_API_KEY is not configured")

        self.client = httpx.AsyncClient(
            base_url=PANEL_URL.rstrip("/") + "/",
            timeout=20.0,
            headers={
                "Accept": "application/json",
                "X-Api-Key": PANEL_API_KEY,
            },
        )

    async def get(self, endpoint: str):
        response = await self.client.get(endpoint.lstrip("/"))
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()
