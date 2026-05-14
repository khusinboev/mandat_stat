import asyncio
import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from config import db


def _run_alembic_upgrade_head() -> None:
    """Apply all pending Alembic migrations."""
    root_dir = Path(__file__).resolve().parents[2]
    alembic_ini = root_dir / "alembic.ini"

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(root_dir / "alembic"))
    command.upgrade(cfg, "head")


async def create_all_base() -> None:
    """Apply schema migrations via Alembic without blocking the event loop."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_alembic_upgrade_head)
