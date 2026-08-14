"""Aggregates all routers so main.py can include them in one call."""
from . import start, water, progress, stats, streaks, settings, pause, help as help_router

all_routers = [
    start.router,
    water.router,
    progress.router,
    stats.router,
    streaks.router,
    settings.router,
    pause.router,
    help_router.router,
]
