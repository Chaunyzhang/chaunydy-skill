from __future__ import annotations

import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryHandler:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.retry_delays = [1, 2, 5]

    async def execute_with_retry(self, func: Callable[..., T], *args, **kwargs) -> T:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    await asyncio.sleep(delay)
        raise last_error
