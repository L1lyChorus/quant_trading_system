"""Application entry point for the Step 1 project foundation."""

from __future__ import annotations

import logging

from config.settings import settings
from database.connection import initialize_database


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Application startup")
    logger.info("Live trading enabled: %s", settings.live_trading_enabled)
    initialize_database()
    logger.info("Account creation placeholder ready")
    logger.info("Trade request/success/failure placeholders ready")


if __name__ == "__main__":
    main()
