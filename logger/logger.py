import logging
import sys
from logging.handlers import RotatingFileHandler
import os
import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, f"scraper_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(name: str = "scraper", level=logging.DEBUG) -> logging.Logger:
    """
    Returns a configured logger with both console and rotating file handlers.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.hasHandlers():
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        ch.setFormatter(ch_formatter)

        # Rotating file handler (5MB max, 3 backups)
        fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        fh.setLevel(level)
        fh_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        fh.setFormatter(fh_formatter)

        # Failed URLs handler - only logs CRITICAL level (5MB max, 3 backups)
        failed_fh = RotatingFileHandler(os.path.join(LOG_DIR, "failed_urls.log"), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
        failed_fh.setLevel(logging.CRITICAL)
        failed_fh_formatter = logging.Formatter("%(asctime)s | %(message)s")
        failed_fh.setFormatter(failed_fh_formatter)


        logger.addHandler(ch)
        logger.addHandler(fh)
        logger.addHandler(failed_fh)

    return logger
