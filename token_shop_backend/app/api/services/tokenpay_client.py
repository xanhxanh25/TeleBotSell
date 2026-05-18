from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict
import httpx

from app.config import settings
from app.services.tokenpay_signature import create_order_with_signature

def _strip_data_image_prefix(qr: str | None) -> str | None:
    if not qr:
        return None
    # TokenPay thường trả: data:image/png;base64,xxxx
    if qr.startswith("data:image"):
        parts = qr.split("base64,", 1)
        return parts[1] if len(parts) == 2 else qr
    return qr

class TokenPayClient:
    def __init__(self):
        self.base = str(settings.TOKENPAY_API_BASE).rstrip("/")
        self.api_token = settings.TOKENPAY_API_TOKEN

    def create_order(self, out_order_id: str, order_user_key: str, actual_amount: float, currency: str) -> Dict[str, Any]:
        notify_url = f"{str(settings.PUBLIC_BASE_URL).rstrip('/')}/pay/tokenpay/notify_url"
        redirect_url = f"{str(settings.PUBLIC_BASE_URL).rstrip('/')}/pay/tokenpay/return_url?order_id={out_order_id}"

        payload = create_order_with_signature(
            out_order_id=out_order_id,
            order_user_key=order_user_key,
            actual_amount=actual_amount,
            currency=currency,
            api_token=self.api_token,
            notify_url=notify_url,
            redirect_url=redirect_url,
        )

        url = f"{self.base}/CreateOrder"
        with httpx.Client(timeout=20) as client:
            r = client.post(url, json=payload, headers={"Content-Type": "application/json"})
            r.raise_for_status()
            data = r.json()

        # data format theo sample: {'success': True, 'data': payment_url, 'info': {...}}
        if not isinstance(data, dict) or not data.get("success"):
            raise RuntimeError(f"tokenpay_create_failed:{data}")

        info = data.get("info") or {}
        return {
            "success": True,
            "payment_url": data.get("data"),
            "info": {
                "ToAddress": info.get("ToAddress"),
                "QrCodeBase64": _strip_data_image_prefix(info.get("QrCodeBase64")),
                "QrCodeLink": info.get("QrCodeLink"),
                "ExpireTime": info.get("ExpireTime"),
                "Currency": info.get("Currency") or currency,
                "BaseCurrency": info.get("BaseCurrency") or "USD",
                "Amount": info.get("Amount"),
                "ActualAmount": info.get("ActualAmount") or actual_amount,
                "Id": info.get("Id"),
                "BlockChainName": info.get("BlockChainName"),
                "CurrencyName": info.get("CurrencyName"),
            }
        }
