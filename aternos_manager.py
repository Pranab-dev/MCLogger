from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

log = logging.getLogger("mclogger.aternos")

_SESSION_FILE = Path(".aternos_session")
_BASE_URL = "https://aternos.org"

_DIRECT_TOKEN_RE = re.compile(
    r'AJAX_TOKEN["\'\]]*\s*=\s*["\']([A-Za-z0-9_]{16,32})["\']'
)
_AJAX_STMT_RE = re.compile(
    r'window\[["\']AJAX_TOKEN["\']\]\s*=\s*([^;\n]+)',
    re.IGNORECASE,
)
_MAP_REVERSE_ARRAY_RE = re.compile(
    r'\[((?:\s*["\'][A-Za-z0-9_]+["\']\s*,?)+)\]\s*\.map\(\s*\w+\s*=>\s*\w+\.split\(["\']["\']\)\.reverse\(\)\.join\(["\']["\']\)\)'
)
_ARRAY_REVERSE_JOIN_RE = re.compile(
    r'\[((?:\s*["\'][A-Za-z0-9_]+["\']\s*,?)+)\]\s*\.reverse\(\)\.join\(["\']["\']\)'
)
_ARRAY_JOIN_RE = re.compile(
    r'\[((?:\s*["\'][A-Za-z0-9_]+["\']\s*,?)+)\]\s*\.join\(["\']["\']\)'
)
_STRING_LITERAL_RE = re.compile(r'["\']([A-Za-z0-9_]+)["\']')
_ATOB_RE = re.compile(r"atob\(['\"]([A-Za-z0-9+/=]+)['\"]\)")
_LAST_STATUS_RE = re.compile(r"var\s+lastStatus\s*=\s*(\{.*?\})\s*;", re.DOTALL)
_SERVER_ID_RE = re.compile(
    r'data-id=["\']([a-zA-Z0-9]{12,20})["\'][\s\S]{0,600}?server-name["\'][^>]*>\s*([^<\s]+)',
    re.IGNORECASE,
)
_ANY_SERVER_ID_RE = re.compile(r'data-id=["\']([a-zA-Z0-9]{12,20})["\']')
_BANNED_PLAYER_RE = re.compile(
    r'class=["\'][^"\']*list-name[^"\']*["\'][^>]*>\s*([^<\n\r]+?)\s*<',
    re.IGNORECASE,
)


class AternosManager:
    """Session-based Aternos client for /start, /unban, /status, and random-world guard."""

    def __init__(self, config) -> None:
        self.config = config
        self._lock = asyncio.Lock()
        self._scraper: Any = None
        self._ajax_token: str | None = None
        self._server_id: str | None = None
        self.known_banned: bool = False

    def is_configured(self) -> bool:
        return bool(self.config.aternos_session or _SESSION_FILE.is_file())

    def _extract_ajax_token(self, html: str) -> str | None:
        match = _DIRECT_TOKEN_RE.search(html)
        if match:
            return match.group(1)

        for stmt_match in _AJAX_STMT_RE.finditer(html):
            expr = stmt_match.group(1)

            for rev_match in _MAP_REVERSE_ARRAY_RE.finditer(expr):
                parts = _STRING_LITERAL_RE.findall(rev_match.group(1))
                candidate = "".join(p[::-1] for p in parts)
                if 16 <= len(candidate) <= 32:
                    return candidate

            for arr_rev in _ARRAY_REVERSE_JOIN_RE.finditer(expr):
                parts = _STRING_LITERAL_RE.findall(arr_rev.group(1))
                candidate = "".join(reversed(parts))
                if 16 <= len(candidate) <= 32:
                    return candidate

            for arr_join in _ARRAY_JOIN_RE.finditer(expr):
                parts = _STRING_LITERAL_RE.findall(arr_join.group(1))
                candidate = "".join(parts)
                if 16 <= len(candidate) <= 32:
                    return candidate

            ternary_str = re.search(r'\?\s*["\']([A-Za-z0-9_]{16,32})["\']', expr)
            if ternary_str:
                return ternary_str.group(1)

            node_bin = shutil.which("node") or shutil.which("nodejs")
            if node_bin:
                try:
                    js_code = (
                        "const window = globalThis; "
                        "window.document = {currentScript: {}}; "
                        "window.setTimeout = () => {}; "
                        "window.Map = Map; "
                        f"window['AJAX_TOKEN'] = {expr}; "
                        "if (typeof window['AJAX_TOKEN'] === 'string') "
                        "process.stdout.write(window['AJAX_TOKEN']);"
                    )
                    out = (
                        subprocess.check_output(
                            [node_bin, "-e", js_code],
                            timeout=3,
                            stderr=subprocess.DEVNULL,
                        )
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
                    if re.fullmatch(r"[A-Za-z0-9_]{16,32}", out):
                        return out
                except Exception:
                    pass

        for rev_match in _MAP_REVERSE_ARRAY_RE.finditer(html):
            parts = _STRING_LITERAL_RE.findall(rev_match.group(1))
            candidate = "".join(p[::-1] for p in parts)
            if 16 <= len(candidate) <= 32:
                return candidate

        decoded_parts: list[str] = []
        for b64_match in _ATOB_RE.finditer(html):
            try:
                decoded = base64.b64decode(b64_match.group(1)).decode(
                    "utf-8", errors="ignore"
                )
                decoded_parts.append(decoded)
                if re.fullmatch(r"[A-Za-z0-9_]{20}", decoded):
                    return decoded
            except Exception:
                continue

        combined = "".join(decoded_parts)
        token_match = re.search(r"[A-Za-z0-9_]{20}", combined)
        if token_match:
            return token_match.group(0)

        if self.config.aternos_token:
            return self.config.aternos_token

        return None

    def _is_cloudflare_blocked(self, resp: Any) -> bool:
        text_lower = (resp.text or "")[:2000].lower()
        return (
            resp.status_code in (403, 503)
            or "just a moment..." in text_lower
            or "cf-browser-verification" in text_lower
            or "challenge-platform" in text_lower
        )

    def _make_sec(self, scraper: Any) -> str:
        key = secrets.token_hex(8)
        val = secrets.token_hex(8)
        scraper.cookies.set(f"ATERNOS_SEC_{key}", val, domain="aternos.org")
        return f"{key}:{val}"

    def _ajax_request(
        self,
        scraper: Any,
        path: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        if not self._ajax_token:
            resp = scraper.get(f"{_BASE_URL}/server/", timeout=15)
            self._ajax_token = self._extract_ajax_token(resp.text)
            if not self._ajax_token:
                raise RuntimeError(
                    "Could not extract Aternos AJAX_TOKEN from /server/ (session may be expired)."
                )

        sec = self._make_sec(scraper)
        query = dict(params or {})
        query["SEC"] = sec
        query["TOKEN"] = self._ajax_token

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{_BASE_URL}/server/",
        }

        url = f"{_BASE_URL}{path}"
        if method.upper() == "POST":
            return scraper.post(
                url, params=query, data=data, headers=headers, timeout=15
            )
        return scraper.get(url, params=query, headers=headers, timeout=15)

    def _ensure_logged_in_sync(self, force_refresh: bool = False) -> Any:
        if cloudscraper is None:
            raise RuntimeError("cloudscraper is not installed yet.")

        if (
            not force_refresh
            and self._scraper is not None
            and self._server_id
            and self._ajax_token
        ):
            return self._scraper

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        scraper.cookies.set("ATERNOS_LANGUAGE", "en", domain="aternos.org")
        self._ajax_token = None

        session_cookie = ""
        saved_token = ""
        if not force_refresh and _SESSION_FILE.is_file():
            try:
                saved = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
                session_cookie = saved.get("ATERNOS_SESSION", "")
                self._server_id = saved.get("ATERNOS_SERVER") or None
                saved_token = saved.get("AJAX_TOKEN", "")
            except Exception:
                session_cookie = _SESSION_FILE.read_text(encoding="utf-8").strip()

        if not session_cookie and self.config.aternos_session:
            session_cookie = self.config.aternos_session

        env_server_id = os.getenv("ATERNOS_SERVER", "").strip()
        if env_server_id and not self._server_id:
            self._server_id = env_server_id

        if not session_cookie:
            raise RuntimeError(
                "ATERNOS_SESSION is missing in .env. Add your Aternos browser session cookie."
            )

        scraper.cookies.set("ATERNOS_SESSION", session_cookie, domain="aternos.org")
        if self._server_id:
            scraper.cookies.set("ATERNOS_SERVER", self._server_id, domain="aternos.org")

        servers_resp = scraper.get(f"{_BASE_URL}/servers/", timeout=15)
        if self._is_cloudflare_blocked(servers_resp):
            raise RuntimeError(
                "Cloudflare blocked this host IP on aternos.org. Try again in a moment."
            )

        if "/go/" in servers_resp.url or "login" in servers_resp.url.lower():
            if _SESSION_FILE.is_file():
                try:
                    _SESSION_FILE.unlink()
                except Exception:
                    pass
            raise RuntimeError(
                "ATERNOS_SESSION cookie is expired or invalid. Grab a fresh ATERNOS_SESSION "
                "cookie from your browser and update .env."
            )

        target_sub = self.config.aternos_subdomain.casefold()
        chosen_id = self._server_id
        for srv_id, srv_name in _SERVER_ID_RE.findall(servers_resp.text):
            if srv_name.strip().casefold() == target_sub:
                chosen_id = srv_id
                break

        if not chosen_id:
            all_ids = _ANY_SERVER_ID_RE.findall(servers_resp.text)
            if all_ids:
                chosen_id = all_ids[0]

        if not chosen_id:
            raise RuntimeError("Could not locate any server on this Aternos account.")

        self._server_id = chosen_id
        scraper.cookies.set("ATERNOS_SERVER", chosen_id, domain="aternos.org")

        server_page = scraper.get(f"{_BASE_URL}/server/", timeout=15)
        self._ajax_token = (
            self._extract_ajax_token(server_page.text)
            or self._extract_ajax_token(servers_resp.text)
            or saved_token
            or self.config.aternos_token
        )

        current_session = scraper.cookies.get("ATERNOS_SESSION") or session_cookie
        if current_session:
            try:
                _SESSION_FILE.write_text(
                    json.dumps(
                        {
                            "ATERNOS_SESSION": current_session,
                            "ATERNOS_SERVER": self._server_id,
                            "AJAX_TOKEN": self._ajax_token or "",
                        }
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass

        self._scraper = scraper
        return scraper

    def _run_with_refresh(self, action):
        try:
            scraper = self._ensure_logged_in_sync(force_refresh=False)
            return action(scraper)
        except RuntimeError:
            raise
        except Exception:
            log.info("Cached Aternos session failed; rebuilding session from .env.")
            self._scraper = None
            scraper = self._ensure_logged_in_sync(force_refresh=True)
            return action(scraper)

    def _fetch_server_status_sync(self, scraper: Any) -> dict[str, Any]:
        resp = scraper.get(f"{_BASE_URL}/server/", timeout=15)
        token = self._extract_ajax_token(resp.text)
        if token:
            self._ajax_token = token

        match = _LAST_STATUS_RE.search(resp.text)
        if not match:
            raise RuntimeError("Could not read server status from Aternos page.")
        return json.loads(match.group(1))

    def _fetch_banned_players_sync(self, scraper: Any) -> list[str]:
        resp = scraper.get(f"{_BASE_URL}/players/banned-players", timeout=15)
        return [
            name.strip()
            for name in _BANNED_PLAYER_RE.findall(resp.text)
            if name.strip()
        ]

    async def is_our_server_online(self) -> tuple[bool, str, int | None]:
        """Verify whether OUR configured Aternos server is genuinely online right now."""
        if not self.is_configured():
            return True, "unverified", None

        async with self._lock:
            def _op(scraper: Any) -> tuple[bool, str, int | None]:
                info = self._fetch_server_status_sync(scraper)
                label = str(info.get("label") or info.get("class") or "unknown").lower()
                status_num = info.get("status")
                raw_port = info.get("port")
                actual_port = (
                    int(raw_port)
                    if isinstance(raw_port, (int, str)) and str(raw_port).isdigit()
                    else None
                )
                is_online = status_num in (1, 2, 3, 10) or label in (
                    "online",
                    "starting",
                    "loading",
                    "preparing",
                )
                return is_online, label, actual_port

            try:
                return await asyncio.to_thread(self._run_with_refresh, _op)
            except Exception as exc:
                log.debug("Could not verify Aternos server status: %s", exc)
                return True, "api_error", None

    async def get_status_report(self) -> tuple[str, str]:
        """Return (aternos_server_status_line, ban_status_line) for /status."""
        target_username = self.config.mc_username.strip()

        if not self.is_configured():
            ban_str = (
                f"🔴 **BANNED** (`{target_username}` — detected on join attempt)"
                if self.known_banned
                else f"🟢 Not Banned (`{target_username}`)"
            )
            return (
                "⚠️ Not configured (set `ATERNOS_SESSION` in `.env`)",
                ban_str,
            )

        async with self._lock:
            def _op(scraper: Any) -> tuple[str, str]:
                info = self._fetch_server_status_sync(scraper)
                label = str(info.get("label") or info.get("class") or "unknown").lower()
                status_num = info.get("status")

                if status_num == 1 or label == "online":
                    srv_line = f"🟢 Online (`{self.config.mc_host}`)"
                elif status_num in (2, 3, 10) or label in (
                    "starting",
                    "loading",
                    "preparing",
                    "queue",
                ):
                    srv_line = f"🟡 {label.capitalize()} (`{self.config.mc_host}`)"
                else:
                    srv_line = f"🔴 {label.capitalize()} (`{self.config.mc_host}`)"

                banned_players = self._fetch_banned_players_sync(scraper)
                is_banned = self.known_banned or any(
                    entry.casefold() == target_username.casefold()
                    for entry in banned_players
                )
                self.known_banned = is_banned

                if is_banned:
                    ban_line = (
                        f"🔴 **BANNED** (`{target_username}` — run `/unban` to fix)"
                    )
                else:
                    ban_line = f"🟢 Not Banned (`{target_username}`)"

                return srv_line, ban_line

            try:
                return await asyncio.to_thread(self._run_with_refresh, _op)
            except Exception as exc:
                log.warning("Could not fetch Aternos status report: %s", exc)
                fallback_ban = (
                    f"🔴 **BANNED** (`{target_username}`)"
                    if self.known_banned
                    else f"🟢 Not Banned (`{target_username}`)"
                )
                return (
                    f"⚠️ Unavailable (`{exc}`)",
                    fallback_ban,
                )

    async def start_server(self) -> tuple[bool, str]:
        """Start the Aternos server if it is currently offline."""
        async with self._lock:
            def _op(scraper: Any) -> tuple[bool, str]:
                info = self._fetch_server_status_sync(scraper)
                label = str(info.get("label") or info.get("class") or "unknown").lower()
                status_num = info.get("status")

                if status_num in (1, 2, 3, 10) or label in (
                    "online",
                    "starting",
                    "loading",
                    "preparing",
                    "queue",
                ):
                    return (
                        False,
                        f"ℹ️ Server **{self.config.mc_host}** is already **{label}**.",
                    )

                resp = self._ajax_request(
                    scraper,
                    "/panel/ajax/start.php",
                    method="GET",
                    params={"headstart": 0, "access-credits": 0},
                )
                data = resp.json() if resp.text.strip().startswith("{") else {}

                if data.get("error") == "eula":
                    self._ajax_request(scraper, "/panel/ajax/eula.php", method="GET")
                    resp = self._ajax_request(
                        scraper,
                        "/panel/ajax/start.php",
                        method="GET",
                        params={"headstart": 0, "access-credits": 0},
                    )
                    data = resp.json() if resp.text.strip().startswith("{") else {}

                if data.get("error"):
                    return (
                        False,
                        f"⚠️ Aternos could not start the server: `{data.get('error')}`",
                    )

                return (
                    True,
                    f"🚀 Start signal sent to **{self.config.mc_host}**! "
                    f"MCLogger will automatically connect once it finishes booting.",
                )

            try:
                return await asyncio.to_thread(self._run_with_refresh, _op)
            except Exception as exc:
                log.exception("Aternos /start failed.")
                return False, f"⚠️ Failed to start Aternos server: `{exc}`"

    async def unban_mclogger(self) -> tuple[bool, str]:
        """Unban ONLY MCLogger on Aternos (works whether the server is online or offline)."""
        target_username = self.config.mc_username.strip()

        async with self._lock:
            def _op(scraper: Any) -> tuple[bool, str]:
                info = self._fetch_server_status_sync(scraper)
                label = str(info.get("label") or info.get("class") or "unknown").lower()

                banned_players = self._fetch_banned_players_sync(scraper)
                matched_entry = None
                for entry in banned_players:
                    if entry.casefold() == target_username.casefold():
                        matched_entry = entry
                        break

                if matched_entry is None and not self.known_banned:
                    return (
                        False,
                        f"ℹ️ **{target_username}** is not currently banned on Aternos "
                        f"(server is **{label}**).",
                    )

                name_to_remove = matched_entry or target_username
                self._ajax_request(
                    scraper,
                    "/panel/ajax/players/remove.php",
                    method="POST",
                    data={"list": "ban", "name": name_to_remove},
                )
                self.known_banned = False

                return (
                    True,
                    f"✅ Unbanned **{name_to_remove}** on Aternos "
                    f"(server status: **{label}**).",
                )

            try:
                return await asyncio.to_thread(self._run_with_refresh, _op)
            except Exception as exc:
                log.exception("Aternos /unban failed.")
                return False, f"⚠️ Failed to unban **{target_username}**: `{exc}`"
