from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")

def with_retry(fn: Callable[[], T], attempts: int = 3, base_sleep: float = 0.25) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(base_sleep * (2 ** i))
    assert last is not None
    raise last
