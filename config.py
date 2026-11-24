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
    aternos_username: str
    aternos_password: str
    aternos_session: str
    aternos_token: str
    aternos_subdomain: str
    admin_user_ids: frozenset[int]
    panel_url: str
    panel_api_key: str
    panel_server_id: str


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


def _clean_cookie(raw: str) -> str:
    val = raw.strip().strip('"').strip("'")
    if val.startswith("ATERNOS_SESSION="):
        val = val[len("ATERNOS_SESSION=") :].strip().strip('"').strip("'")
    return val


def _parse_admin_ids(raw: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise ValueError(
                f"Invalid Discord user ID '{part}' in ADMIN_USER_IDS."
            ) from exc
    return frozenset(ids)


def load_config() -> Config:
    load_dotenv(override=True)

    try:
        port = int(os.getenv("MC_PORT", "15629"))
        reconnect_delay = float(os.getenv("MC_RECONNECT_DELAY", "30"))
    except ValueError as exc:
        raise ValueError("MC_PORT and MC_RECONNECT_DELAY must be numeric.") from exc

    if not 1 <= port <= 65535:
        raise ValueError("MC_PORT must be between 1 and 65535.")
    if reconnect_delay <= 0:
        raise ValueError("MC_RECONNECT_DELAY must be greater than zero.")

    mc_host = os.getenv("MC_HOST", "nexusforever.aternos.me").strip()
    default_subdomain = mc_host.split(".")[0].strip()
    aternos_subdomain = (
        os.getenv("ATERNOS_SUBDOMAIN", default_subdomain).strip()
        or default_subdomain
    )

    return Config(
        discord_token=_required("DISCORD_TOKEN"),
        minecraft_channel_id=_channel_id("MINECRAFT_CHANNEL_ID"),
        bot_log_channel_id=_channel_id("BOT_LOG_CHANNEL_ID"),
        mc_host=mc_host,
        mc_port=port,
        mc_version=os.getenv("MC_VERSION", "26.3").strip(),
        mc_username=os.getenv("MC_USERNAME", "MCLogger").strip(),
        mc_password=_required("MC_PASSWORD"),
        reconnect_delay=reconnect_delay,
        aternos_username=os.getenv("ATERNOS_USERNAME", "").strip(),
        aternos_password=os.getenv("ATERNOS_PASSWORD", "").strip(),
        aternos_session=_clean_cookie(os.getenv("ATERNOS_SESSION", "")),
        aternos_token=os.getenv("ATERNOS_TOKEN", "").strip().strip('"').strip("'"),
        aternos_subdomain=aternos_subdomain,
        admin_user_ids=_parse_admin_ids(os.getenv("ADMIN_USER_IDS", "")),
        panel_url=os.getenv("PANEL_URL", "").strip().rstrip("/"),
        panel_api_key=os.getenv("PANEL_API_KEY", "").strip(),
        panel_server_id=os.getenv("PANEL_SERVER_ID", "").strip(),
            )
    
