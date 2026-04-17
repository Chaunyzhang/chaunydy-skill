from __future__ import annotations

import asyncio
import random
import time


class RateLimiter:
    def __init__(self, max_per_second: float = 1.2):
        if max_per_second <= 0:
            max_per_second = 1.2
        self.min_interval = 1.0 / max_per_second
        self.last_request = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            current = time.time()
            elapsed = current - self.last_request
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request = time.time()
        await asyncio.sleep(random.uniform(0.12, 0.55))
