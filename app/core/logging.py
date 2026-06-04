from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler


def setup_logging():
    # 1. Create a logger
    logger = logging.getLogger("fastapi_app")
    logger.setLevel(logging.INFO)

    # 2. Define the format for the logs
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 3. File Handler (Saves to file, rotates at 5MB, keeps 3 backups)
    file_handler = RotatingFileHandler(
        "app.log", 
        maxBytes=5 * 1024 * 1024, 
        backupCount=3
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # 4. Console Handler (Keeps printing to terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # 5. Add handlers to the logger
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

# Initialize the logger instance
logger = setup_logging()