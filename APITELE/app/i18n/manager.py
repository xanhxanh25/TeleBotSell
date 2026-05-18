from app.i18n.messages import MESSAGES
from app.i18n.coupon_errors import CODE_TO_KEY

SUPPORTED = ("vi", "en", "ru", "zh")
DEFAULT_LANG = "en"  # Mặc định tiếng Anh

def normalize(lang: str | None) -> str:
    if not lang:
        return DEFAULT_LANG
    lang = lang.lower()
    if lang.startswith("vi"):
        return "vi"
    if lang.startswith("en"):
        return "en"
    if lang.startswith("ru"):
        return "ru"
    if lang.startswith("zh"):
        return "zh"
    return DEFAULT_LANG

def t(lang: str, key: str, **kwargs) -> str:
    lang = normalize(lang)
    data = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG])
    text = data.get(key) or MESSAGES[DEFAULT_LANG].get(key, key)
    return text.format(**kwargs)


def t_coupon_api_code(lang: str, code: str | None) -> str:
    """Backend coupon_error / checkout detail.code → user-facing string."""
    if not code:
        return t(lang, "coupon_invalid")
    key = CODE_TO_KEY.get(str(code).strip())
    if not key:
        return t(lang, "coupon_invalid")
    return t(lang, key)
