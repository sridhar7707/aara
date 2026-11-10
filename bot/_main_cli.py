"""Command-line entry point for the trading bot.

Moved out of bot/main.py to keep that file under the 500-line limit. bot/main.py still
runs this when executed as a script (python bot/main.py ...), so the workflows are
unchanged. The dispatch targets are imported from bot.main, so tests that patch
bot.main keep working.
"""
import argparse
import sys
import traceback

from loguru import logger

from bot.main import (
    _do_clean_db,
    _do_reset_daily_start,
    end_of_day_summary,
    run,
    run_loop,
)


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
            _do_clean_db()
        elif args.reset_daily_start:
            _do_reset_daily_start()
        elif args.summary:
            end_of_day_summary()
        elif args.loop:
            run_loop(mode=args.mode)
        else:
            run(mode=args.mode)
    except Exception:  # noqa: BLE001 -- top-level crash handler: log, alert the workflow, exit 1
        tb = traceback.format_exc()
        logger.error("Bot crashed:\n" + tb)
        sys.stdout.write(f"::error title=Trading Bot Crash::{tb.splitlines()[-1]} — see step log\n")
        sys.stdout.flush()
        sys.exit(1)
