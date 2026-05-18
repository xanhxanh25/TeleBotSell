import secrets
from datetime import datetime

def make_order_code(telegram_id: int) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rnd = secrets.token_hex(3)
    return f"ORD_{telegram_id}_{ts}_{rnd}".upper()

def make_topup_out_order_id(telegram_id: int) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rnd = secrets.token_hex(3)
    return f"TOPUP_{telegram_id}_{ts}_{rnd}".upper()
