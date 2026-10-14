import logging
import tempfile
import unittest
from pathlib import Path

from endorsement_scraper.logging_config import configure_logging


class LoggingTests(unittest.TestCase):
    def test_separates_general_warnings_and_serious_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            configure_logging(log_directory=Path(temporary))
            logger = logging.getLogger("logging-test")
            logger.info("useful information")
            logger.warning("recoverable warning")
            logger.error("actionable failure")
            for handler in logging.getLogger().handlers:
                handler.flush()

            general = (Path(temporary) / "general.log").read_text(encoding="utf-8")
            warnings = (Path(temporary) / "warnings.log").read_text(encoding="utf-8")
            errors = (Path(temporary) / "errors.log").read_text(encoding="utf-8")
            self.assertIn("useful information", general)
            self.assertIn("recoverable warning", warnings)
            self.assertNotIn("actionable failure", warnings)
            self.assertIn("actionable failure", errors)
            # Release Windows file handles before TemporaryDirectory cleanup.
            configure_logging(log_directory=Path("logs"))


if __name__ == "__main__":
    unittest.main()
