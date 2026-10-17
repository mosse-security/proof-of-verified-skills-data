"""Central logging configuration for command-line runs."""
from __future__ import annotations

import logging
from pathlib import Path


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(threadName)s %(message)s"
_HANDLER_MARKER = "verified-endorsement-file-handler"


class ExactLevelFilter(logging.Filter):
    def __init__(self, level: int) -> None:
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self.level


def configure_logging(*, level: int = logging.INFO, log_directory: Path = Path("logs")) -> None:
    """Configure console plus separate general, warning, and error files."""
    log_directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "_verified_endorsement_handler", False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT)
    general = logging.FileHandler(log_directory / "general.log", encoding="utf-8")
    general.setLevel(level)
    warning = logging.FileHandler(log_directory / "warnings.log", encoding="utf-8")
    warning.setLevel(logging.WARNING)
    warning.addFilter(ExactLevelFilter(logging.WARNING))
    error = logging.FileHandler(log_directory / "errors.log", encoding="utf-8")
    error.setLevel(logging.ERROR)
    for handler in (general, warning, error):
        handler.setFormatter(formatter)
        setattr(handler, "_verified_endorsement_handler", True)
        root.addHandler(handler)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    setattr(console, "_verified_endorsement_handler", True)
    root.addHandler(console)
