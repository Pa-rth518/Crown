"""CLI entry: configure logging and run the prediction pipeline."""

from __future__ import annotations

import argparse
import logging
import sys

from agents.exceptions import AgentError
from config import KLINE_INTERVAL_CHOICES, Settings, get_settings
from pipeline import run_pipeline
from services.logging_setup import configure_logging


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crown",
        description="Crypto direction pipeline: Search → Data → Prediction → Risk → Feedback",
        epilog="Example: python main.py -i 15m    python main.py --log-file logs/run.log -l DEBUG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--interval",
        choices=list(KLINE_INTERVAL_CHOICES),
        default=None,
        metavar="TF",
        help="Kline timeframe override (e.g. 5m vs 15m; default from config/env).",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default=None,
        help="Override LOG_LEVEL for this run.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Append logs to this file (overrides LOG_FILE_PATH when set).",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Do not print the --- Results --- summary block.",
    )
    return parser.parse_args(argv)


def _settings_with_cli_overrides(base: Settings, args: argparse.Namespace) -> Settings:
    updates: dict[str, object] = {}
    if args.interval is not None:
        updates["kline_interval"] = args.interval
    if args.log_level is not None:
        updates["log_level"] = args.log_level
    if args.log_file is not None:
        updates["log_file_path"] = args.log_file
    return base.model_copy(update=updates) if updates else base


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        base_settings = get_settings()
    except Exception as exc:  # pragma: no cover - misconfiguration
        configure_logging("INFO")
        logging.getLogger(__name__).error("Failed to load settings: %s", exc)
        return 1

    settings = _settings_with_cli_overrides(base_settings, args)
    configure_logging(settings.log_level, log_file=settings.log_file_path)

    log = logging.getLogger(__name__)
    log.debug("Effective kline_interval=%s", settings.kline_interval)

    try:
        run_pipeline(settings, print_summary=not args.quiet)
    except AgentError as exc:
        log.error("Pipeline aborted: %s", exc)
        return 3
    except Exception:
        log.exception("Pipeline failed with unexpected error")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
