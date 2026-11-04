"""The app's own logs (`app.*`, INFO and above) on stderr, next to uvicorn's.

Uvicorn configures only its own loggers; without this, the app's INFO logs (AI fill cost and
timing, rejected citations) would be dropped.
"""

import logging


def configure_logging() -> None:
    logger = logging.getLogger("app")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
