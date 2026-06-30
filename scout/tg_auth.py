"""Interactive CLI for first-time Telethon session authorization.

Usage:
    python -m scout.tg_auth [--password SECRET]
    make tg-auth              # авторизует следующий аккаунт автоматически
    make tg-auth SESSION=data/tg_session_5  # конкретный путь
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from scout.config import settings


def _proxy_kwargs() -> dict:
    """Build Telethon proxy arg from HTTP_PROXY env."""
    if not settings.HTTP_PROXY:
        return {}
    parsed = urlparse(settings.HTTP_PROXY)
    if parsed.scheme in ("http", "https"):
        return {"proxy": ("http", parsed.hostname, parsed.port)}
    if parsed.scheme in ("socks5", "socks4"):
        return {"proxy": (parsed.scheme, parsed.hostname, parsed.port)}
    return {}


def _next_session_path() -> str:
    """Find next free session path: data/tg_session, data/tg_session_2, ..."""
    base = Path(settings.TG_SESSION_PATH)
    # First slot: data/tg_session
    if not base.with_suffix(".session").exists():
        return str(base)
    # data/tg_session_2, _3, ...
    i = 2
    while True:
        candidate = base.parent / f"{base.name}_{i}"
        if not candidate.with_suffix(".session").exists():
            return str(candidate)
        i += 1


def _list_sessions() -> list[str]:
    """List all existing authorized sessions."""
    base = Path(settings.TG_SESSION_PATH)
    sessions = sorted(base.parent.glob(f"{base.name}*.session"))
    return [str(s.with_suffix("")) for s in sessions]


async def authorize(password: str | None = None, session_path: str | None = None) -> None:
    if not settings.TG_API_ID or not settings.TG_API_HASH:
        print("ERROR: TG_API_ID and TG_API_HASH must be set in .env")
        print("Get them at https://my.telegram.org/apps")
        sys.exit(1)

    sess = session_path or _next_session_path()

    # Show existing sessions
    existing = _list_sessions()
    if existing:
        print(f"Существующие сессии ({len(existing)}):")
        for s in existing:
            print(f"  {s}.session")
        print()

    print(f"Новая сессия: {sess}.session")
    phone = input("Номер телефона (с кодом страны, напр. +79001234567): ").strip()

    proxy = _proxy_kwargs()
    if proxy:
        print(f"Using proxy: {settings.HTTP_PROXY}")

    Path(sess).parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(
        sess, settings.TG_API_ID, settings.TG_API_HASH,
        **proxy,
    )
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Уже авторизован: {me.first_name} (@{me.username or 'N/A'})")
        await client.disconnect()
        return

    await client.send_code_request(phone)
    code = input("Введите код из Telegram: ").strip()

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        pwd = password or os.getenv("TG_2FA_PASSWORD") or ""
        if not pwd:
            pwd = input("Пароль двухфакторной авторизации: ").strip()
        await client.sign_in(password=pwd)

    me = await client.get_me()
    print(f"\nАвторизован: {me.first_name} (@{me.username or 'N/A'})")
    print(f"Сессия сохранена: {sess}.session")

    # Show what to put in .env
    all_sessions = _list_sessions()
    paths_value = ",".join(all_sessions)
    print(f"\nДля .env:\nTG_SESSION_PATHS={paths_value}")

    await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Telethon authorization")
    parser.add_argument("--password", "-p", default=None, help="2FA password")
    parser.add_argument("--session", "-s", default=None, help="Session path (auto if omitted)")
    args = parser.parse_args()
    asyncio.run(authorize(password=args.password, session_path=args.session))


if __name__ == "__main__":
    main()
