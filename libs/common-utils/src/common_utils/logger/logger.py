# app/logger.py

import logging
from logging.handlers import TimedRotatingFileHandler
import os
from datetime import datetime, timezone

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# ===== Configure Logger =====
logger = logging.getLogger("Gremory")
logger.setLevel(logging.DEBUG)

# ===== Formatter (UTC time) =====
class UTCFormatter(logging.Formatter):
    converter = lambda *args: datetime.now(tz=timezone.utc).timetuple()
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S UTC")

formatter = UTCFormatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s.%(funcName)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S UTC"
)

# ===== Console Handler =====
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ===== File Handler (Rotates Daily) =====
log_file = "logs/gremory.log"
file_handler = TimedRotatingFileHandler(
    log_file,
    when="midnight",
    interval=1,
    backupCount=60,                    # keep last 7 days
    utc=True                          # Rotate at UTC midnight
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Prevent duplicate logs in Uvicorn
logger.propagate = False
