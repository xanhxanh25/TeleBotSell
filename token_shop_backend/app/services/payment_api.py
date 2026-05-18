# app/services/payment_api.py
class PaymentAPI:
    def __init__(self, http, base: str):
        self.http = http
        self.base = base.rstrip("/")

    async def create_topup(self, telegram_id: int, network: str, coin: str, amount: float, telegram_user: str | None = None) -> dict:
        payload = {"telegram_id": telegram_id, "network": network, "coin": coin, "amount": amount}
        if telegram_user:
            payload["telegram_user"] = telegram_user
        return await self.http.request(
            "POST",
            f"{self.base}/topups/create",
            json=payload,
        )

    async def get_topup(self, topup_id: str) -> dict:
        return await self.http.request("GET", f"{self.base}/topups/{topup_id}")

    async def cancel_topup(self, telegram_id: int, topup_id: str) -> dict:
        # backend cancel nhận telegram_id dạng query param
        return await self.http.request("POST", f"{self.base}/topups/{topup_id}/cancel?telegram_id={telegram_id}")
