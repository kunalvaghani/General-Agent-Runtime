"""Configure GAR logging without replacing the host application's handlers."""

import logging


def configure_logging(level: str = "INFO") -> None:
    logger = logging.getLogger("gar")
    logger.setLevel(level)
    if not any(getattr(handler, "_gar_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler._gar_handler = True
        logger.addHandler(handler)
    logger.propagate = False
