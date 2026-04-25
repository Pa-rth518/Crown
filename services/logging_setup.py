"""Central logging configuration for CLI and library use."""

from __future__ import annotations

import logging
import sys
from typing import TextIO


def configure_logging(
    level: str = "INFO",
    *,
    log_file: str | None = None,
    stream: TextIO | None = None,
) -> None:
    """
    Configure the root logger once: console handler always, optional file handler.

    Clears existing root handlers to avoid duplicate lines when re-run in tests.
    """
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()

    resolved = getattr(logging, level.upper(), logging.INFO)
    if not isinstance(resolved, int):
        resolved = logging.INFO

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    out = stream if stream is not None else sys.stdout
    sh = logging.StreamHandler(out)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)

    root.setLevel(resolved)
