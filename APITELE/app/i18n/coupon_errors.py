"""Map backend coupon error codes to i18n keys (see messages.py)."""

CODE_TO_KEY = {
    "COUPON_INVALID": "coupon_err_invalid",
    "COUPON_EXPIRED": "coupon_err_expired",
    "COUPON_INACTIVE": "coupon_err_inactive",
    "COUPON_NOT_STARTED": "coupon_err_not_started",
    "COUPON_WRONG_PRODUCT": "coupon_err_wrong_product",
    "COUPON_WRONG_USER": "coupon_err_wrong_user",
    "COUPON_ALREADY_USED_BY_USER": "coupon_err_already_used",
    "COUPON_MAX_USES_EXCEEDED": "coupon_err_max_uses",
    "COUPON_MIN_ORDER_NOT_MET": "coupon_err_min_order",
    "COUPON_MAX_QTY_EXCEEDED": "coupon_err_max_qty",
}
