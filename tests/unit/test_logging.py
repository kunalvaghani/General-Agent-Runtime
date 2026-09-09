import logging

from gar.logging import configure_logging


def test_logging_is_idempotent_and_preserves_root(capsys):
    logger = logging.getLogger("gar")
    original_handlers = logger.handlers[:]
    original_level, original_propagate = logger.level, logger.propagate
    root_handlers = logging.getLogger().handlers[:]
    logger.handlers = []
    try:
        configure_logging("INFO")
        configure_logging("DEBUG")
        assert len(logger.handlers) == 1
        assert logger.level == logging.DEBUG
        assert logging.getLogger().handlers == root_handlers
        logging.getLogger("gar.test").info("bootstrap test")
        assert "INFO gar.test: bootstrap test" in capsys.readouterr().err
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate
