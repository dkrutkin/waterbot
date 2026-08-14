"""Postgres-backed FSM storage for aiogram.

The bot runs two ways: a long-lived local process (main.py, polling) and
Vercel serverless functions (app.py, webhook) that get a fresh process per
invocation with no shared memory. aiogram's default MemoryStorage only
works for the former — a multi-step conversation (onboarding, "enter a
custom amount", settings text prompts) would lose its place between one
webhook call and the next on Vercel. Storing FSM state/data in the same
Postgres database used for everything else fixes that for both run modes.
"""
import json
from typing import Any, Mapping, Optional

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

import database as db

# The fsm_storage table itself is created by database.py's schema (single
# source of truth for DDL) — see the CREATE TABLE fsm_storage statement there.


def _key_str(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id}:{key.destiny}"


class PostgresStorage(BaseStorage):
    async def set_state(self, key: StorageKey, state: Any = None) -> None:
        state_str = state.state if isinstance(state, State) else state
        async with db.pool().acquire() as c:
            await c.execute(
                """INSERT INTO fsm_storage (storage_key, state, data)
                   VALUES ($1, $2, '{}'::jsonb)
                   ON CONFLICT (storage_key) DO UPDATE SET state = EXCLUDED.state""",
                _key_str(key), state_str,
            )

    async def get_state(self, key: StorageKey) -> Optional[str]:
        async with db.pool().acquire() as c:
            return await c.fetchval(
                "SELECT state FROM fsm_storage WHERE storage_key = $1", _key_str(key)
            )

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        async with db.pool().acquire() as c:
            await c.execute(
                """INSERT INTO fsm_storage (storage_key, state, data)
                   VALUES ($1, NULL, $2::jsonb)
                   ON CONFLICT (storage_key) DO UPDATE SET data = EXCLUDED.data""",
                _key_str(key), json.dumps(dict(data)),
            )

    async def get_data(self, key: StorageKey) -> dict:
        async with db.pool().acquire() as c:
            raw = await c.fetchval(
                "SELECT data FROM fsm_storage WHERE storage_key = $1", _key_str(key)
            )
        if not raw:
            return {}
        return json.loads(raw) if isinstance(raw, str) else dict(raw)

    async def close(self) -> None:
        # Connection pool lifecycle is owned by database.py, nothing to do here.
        pass
