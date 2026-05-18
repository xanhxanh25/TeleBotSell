from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def kb_topup_methods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        # ── Binance ID Pay ────────────────────────────────────────────────
        [InlineKeyboardButton(
            text="🟠  USDT — Binance ID Pay (P2P)",
            callback_data="topup:net:BINANCE:USDT_BSC",
        )],
        # ── On-chain wallets ──────────────────────────────────────────────
        [InlineKeyboardButton(
            text="🟡  USDT — BSC (BEP20)",
            callback_data="topup:net:BSC:USDT_BEP20",
        )],
        [InlineKeyboardButton(
            text="🟣  USDT — Polygon",
            callback_data="topup:net:POLYGON:USDT-ERC20",
        )],
        [InlineKeyboardButton(
            text="🔵  USDT — Ethereum (ERC20)",
            callback_data="topup:net:ETH:USDT_ERC20",
        )],
        # ─────────────────────────────────────────────────────────────────
        [InlineKeyboardButton(
            text="❌  Cancel",
            callback_data="topup:cancel",
        )],
    ])


def kb_topup_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌  Cancel", callback_data="topup:cancel")],
    ])


def kb_topup_pending_actions(topup_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌  Cancel pending topup",
            callback_data=f"topup:cancel_pending:{topup_id}",
        )],
    ])
