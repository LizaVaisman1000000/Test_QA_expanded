import logging
import os
from datetime import datetime


class TestLogger:
    """Writes the log messages of one test to its own timestamped file."""

    def __init__(self, test_name: str, log_dir: str = "results/logs"):
        self._test_name = test_name
        self._log_dir = log_dir
        self.log_file = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        os.makedirs(self._log_dir, exist_ok=True)

        # The file name holds the time and the test name, so every run gets its own file.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = f"{self._log_dir}/{timestamp}_{self._test_name}.log"

        logger = logging.getLogger(f"test_{self._test_name}")

        # Fix: the original never set a level, so info/debug messages were dropped.
        logger.setLevel(logging.DEBUG)
        # Do not pass messages on to the root logger, which would print them a second time.
        logger.propagate = False

        # getLogger() returns the SAME object for the same name. Remove handlers from
        # an earlier TestLogger with this name, or every line would be written twice.
        for old_handler in list(logger.handlers):
            old_handler.close()
            logger.removeHandler(old_handler)

        # Fix: the original never attached a handler, so nothing was ever written.
        handler = logging.FileHandler(self.log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        return logger

    def info(self, message: str):
        self.logger.info(message)

    def error(self, message: str):
        self.logger.error(message)

    def debug(self, message: str):
        self.logger.debug(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def close(self):
        """Release the log file (important on Windows, where open files cannot be deleted)."""
        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)