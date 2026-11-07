"""Shared test helpers."""

import asyncio
from collections.abc import Callable


async def wait_until(condition: Callable[[], bool], timeout: float = 2.0) -> None:
    """Poll `condition` until true; fail the test if it is still false after `timeout`."""
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.005)
