import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str):
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "bot.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    # tránh add handler nhiều lần
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console)
