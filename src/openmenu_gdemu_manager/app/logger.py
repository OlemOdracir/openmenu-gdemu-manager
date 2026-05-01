import logging
import sys
import traceback

from ..config.paths import LOG_PATH


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    sys.excepthook = log_uncaught_exception
    logging.getLogger(__name__).info("Logging initialized: %s", LOG_PATH)


def log_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    logging.getLogger("uncaught").critical(
        "Unhandled exception\n%s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
    )

