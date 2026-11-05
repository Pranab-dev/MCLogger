from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    discord_token: str
    minecraft_channel_id: int
    bot_log_channel_id: int
    mc_host: str
    mc_port: int
    mc_version: str
    mc_username: str
    mc_password: str
    reconnect_delay: float


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("PUT_YOUR_"):
        raise ValueError(f"Set {name} in your .env file.")
    return value


def _channel_id(name: str) -> int:
    try:
        value = int(_required(name))
    except ValueError as exc:
        raise ValueError(f"{name} must be a numeric Discord channel ID.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive Discord channel ID.")
    return value


def load_config() -> Config:
    load_dotenv()

    try:
        port = int(os.getenv("MC_PORT", "15629"))
        reconnect_delay = float(os.getenv("MC_RECONNECT_DELAY", "30"))
    except ValueError as exc:
        raise ValueError("MC_PORT and MC_RECONNECT_DELAY must be numeric.") from exc

    if not 1 <= port <= 65535:
        raise ValueError("MC_PORT must be between 1 and 65535.")
    if reconnect_delay <= 0:
        raise ValueError("MC_RECONNECT_DELAY must be greater than zero.")

    return Config(
        discord_token=_required("DISCORD_TOKEN"),
        minecraft_channel_id=_channel_id("MINECRAFT_CHANNEL_ID"),
        bot_log_channel_id=_channel_id("BOT_LOG_CHANNEL_ID"),
        mc_host=os.getenv("MC_HOST", "nexusforever.aternos.me").strip(),
        mc_port=port,
        mc_version=os.getenv("MC_VERSION", "26.3").strip(),
        mc_username=os.getenv("MC_USERNAME", "MCLogger").strip(),
        mc_password=_required("MC_PASSWORD"),
        reconnect_delay=reconnect_delay,
    )
