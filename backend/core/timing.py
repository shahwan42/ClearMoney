"""Lightweight performance timing for service operations."""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

logger = logging.getLogger("performance")


def timed(threshold_ms: float = 500) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Log a warning when a function exceeds threshold_ms."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms > threshold_ms:
                logger.warning(
                    "slow_operation fn=%s elapsed_ms=%.1f threshold_ms=%.1f",
                    func.__qualname__,
                    elapsed_ms,
                    threshold_ms,
                )
            return result

        return wrapper

    return decorator
