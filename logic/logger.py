"""Logging Module for GroovyBox."""

import logging
from collections import deque

_MAX_LOG_LINES = 5000

_log_buffer = deque(maxlen=_MAX_LOG_LINES)

LEVEL_MAP = {
    "verbose": logging.DEBUG,
    "normal": logging.INFO,
    "errors_warnings": logging.WARNING,
    "errors_only": logging.ERROR,
}


class _CircularBufferHandler(logging.Handler):
    """Handler that stores log records in a fixed-size circular buffer."""

    def __init__(self, maxlen: int = _MAX_LOG_LINES):
        super().__init__()
        self.buffer = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord):
        self.buffer.append(self.format(record))


def _setup_logger():
    logger = logging.getLogger("GroovyBox")
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", datefmt="%H:%M:%S")

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    bh = _CircularBufferHandler(_MAX_LOG_LINES)
    bh.setFormatter(formatter)
    logger.addHandler(bh)

    return logger


logger = _setup_logger()


def set_log_level(level_name: str):
    lvl = LEVEL_MAP.get(level_name, logging.INFO)
    logger.setLevel(lvl)
    for h in logger.handlers:
        h.setLevel(lvl)
    logger.info("Log level set to %s (%d)", level_name, lvl)


def export_logs(path: str):
    for h in logger.handlers:
        if isinstance(h, _CircularBufferHandler):
            lines = list(h.buffer)
            break
    else:
        lines = []
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
