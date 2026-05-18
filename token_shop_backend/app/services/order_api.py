from typing import Any
from app.services.cache import products_cache, user_balance_cache

class OrderAPI:
    def __init__(self, http, base: str):
        self.http = http
        self.base = base.rstrip("/")

    def _map_lang(self, bot_lang: str) -> str:
        """Map bot language (vi/en/ru/zh) sang API language (vi/en/zh/ru)"""
        # Bot: vi, en, ru, zh
        # API: vi, en, zh, ru
        lang_map = {
            "vi": "vi",
            "en": "en",
            "ru": "ru",  # Russian → Russian
            "zh": "zh",
        }
        return lang_map.get(bot_lang, "en")  # Mặc định en

    async def list_products(self, lang: str = "en") -> list[dict]:
        # Cache products list để giảm request (thread-safe)
        # Cache key bao gồm lang để cache riêng theo ngôn ngữ
        cache_key = f"products_{lang}"
        cached = await products_cache.get(cache_key)
        if cached is not None:
            return cached
        
        # Map bot lang sang API lang
        api_lang = self._map_lang(lang)
        products = await self.http.request("GET", f"{self.base}/public/products?lang={api_lang}")
        # Đảm bảo có đủ thông tin cần thiết
        for p in products:
            if "currency" not in p:
                p["currency"] = "USD"
            if "stock" not in p:
                p["stock"] = 0
        await products_cache.set(cache_key, products)
        return products

    async def get_product(self, product_id: str, lang: str = "en") -> dict:
        # Map bot lang sang API lang
        api_lang = self._map_lang(lang)
        return await self.http.request("GET", f"{self.base}/public/products/{product_id}?lang={api_lang}")

    async def quote(self, telegram_id: int, product_id: str, qty: int, coupon: str | None, telegram_user: str | None = None) -> dict:
        payload = {"telegram_id": telegram_id, "product_id": product_id, "qty": qty, "coupon": coupon}
        if telegram_user:
            payload["telegram_user"] = telegram_user
        return await self.http.request("POST", f"{self.base}/orders/quote", json=payload)

    async def checkout(self, telegram_id: int, product_id: str, qty: int, coupon: str | None, idem_key: str, telegram_user: str | None = None) -> dict:
        # Idempotent bắt buộc: idem_key do bot tạo theo flow + message id
        payload = {
            "telegram_id": telegram_id,
            "product_id": product_id,
            "qty": qty,
            "coupon": coupon,
            "idempotency_key": idem_key,
        }
        if telegram_user:
            payload["telegram_user"] = telegram_user
        result = await self.http.request("POST", f"{self.base}/orders/checkout", json=payload)
        
        # ✅ Clear cache products (tất cả ngôn ngữ) và user balance sau khi mua thành công
        await self.clear_products_cache()
        await user_balance_cache.clear(f"user_me_{telegram_id}")
        
        return result
    
    async def clear_products_cache(self):
        """Clear products cache manually (tất cả ngôn ngữ)"""
        # Clear tất cả cache key bắt đầu bằng "products_"
        async with products_cache._lock:
            keys_to_remove = [key for key in products_cache.cache.keys() if key.startswith("products_")]
            for key in keys_to_remove:
                products_cache.cache.pop(key, None)

    async def history(self, telegram_id: int, month: int | None = None, year: int | None = None, page: int = 1, limit: int = 10) -> dict:
        params = {"telegram_id": telegram_id, "page": page, "limit": limit}
        if month:
            params["month"] = month
        if year:
            params["year"] = year
        return await self.http.request("GET", f"{self.base}/orders/history", params=params)
    
    async def get_order_detail(self, order_id: str, telegram_id: int) -> dict:
        return await self.http.request("GET", f"{self.base}/orders/{order_id}?telegram_id={telegram_id}")
    
    async def me(self, telegram_id: int, telegram_user: str | None = None) -> dict:
        # Cache user balance để giảm API calls
        cache_key = f"user_me_{telegram_id}"
        cached = await user_balance_cache.get(cache_key)
        if cached is not None:
            return cached
        
        params = {"telegram_id": telegram_id}
        if telegram_user:
            params["telegram_user"] = telegram_user
        result = await self.http.request("GET", f"{self.base}/users/me", params=params)
        await user_balance_cache.set(cache_key, result)
        return result