from __future__ import annotations

import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import aiohttp
import discord

from config import load_config
from discord_bot import MCLoggerDiscord


def main() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Keep a persistent daily log and retain the latest 30 rotated files.
    file_handler = TimedRotatingFileHandler(
        log_dir / "mclogger.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        delay=True,
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    try:
        config = load_config()
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print("Copy .env.example to .env and fill in the required values.")
        raise SystemExit(2)

    log = logging.getLogger("mclogger")

    while True:
        client = MCLoggerDiscord(config)
        try:
            client.run(config.discord_token, log_handler=None)
        except KeyboardInterrupt:
            return
        except (
            OSError,
            aiohttp.ClientError,
            discord.GatewayNotFound,
            discord.HTTPException,
        ) as exc:
            log.warning(
                "Discord connection/DNS error (%s). Retrying in 15s without crashing container...",
                exc,
            )
            time.sleep(15)
            continue

        # If /restart was triggered in Discord, re-exec the Python process in-place
        # without exiting the container so Silly Development stays running.
        if getattr(client, "restart_requested", False):
            log.info("Restarting MCLogger backend process in-place...")
            os.execv(sys.executable, [sys.executable, *sys.argv])

        break


if __name__ == "__main__":
    main()
