"""Command-line entry point for the trading bot.

Moved out of bot/main.py to keep that file under the 500-line limit. Run it as
`python -m bot._main_cli ...` (the workflows do this); `python bot/main.py ...` still works
through a delegation in bot/main.py.

Dispatch goes through the bot.main module object, not copied names, so tests that patch
bot.main.run (or any other dispatch target) are honoured.
"""
from __future__ import annotations

import argparse
import sys
import traceback

from loguru import logger

import bot.main as _main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="paper", choices=["paper", "live"])
    parser.add_argument("--summary", action="store_true",
                        help="Send end-of-day Telegram summary and exit")
    parser.add_argument("--loop", action="store_true",
                        help="Long-running mode: load models once, loop until market close")
    parser.add_argument("--reset-daily-start", action="store_true",
                        help="Clear stale daily_start anchor so Day P&L resets on next cycle")
    parser.add_argument("--clean-db", action="store_true",
                        help="Wipe all bot data for a clean start (reset Alpaca paper account first)")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        if args.clean_db:
            _main._do_clean_db()
        elif args.reset_daily_start:
            _main._do_reset_daily_start()
        elif args.summary:
            _main.end_of_day_summary()
        elif args.loop:
            _main.run_loop(mode=args.mode)
        else:
            _main.run(mode=args.mode)
    except Exception:  # noqa: BLE001 -- top-level crash handler: log, alert the workflow, exit 1
        tb = traceback.format_exc()
        logger.error("Bot crashed:\n" + tb)
        sys.stdout.write(f"::error title=Trading Bot Crash::{tb.splitlines()[-1]} — see step log\n")
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
