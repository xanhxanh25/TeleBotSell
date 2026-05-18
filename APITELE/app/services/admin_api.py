class AdminAPI:
    def __init__(self, http, base: str):
        self.http = http
        self.base = base.rstrip("/")

    async def get_broadcasts(self):
        return await self.http.request("GET", f"{self.base}/broadcasts/pull")
