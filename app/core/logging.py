from __future__ import annotations

import logging

def setup_logging():
    logger = logging.getLogger("fastapi_app")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    if not logger.handlers:
        logger.addHandler(console_handler)

    return logger

# Initialize the logger instance
logger = setup_logging()