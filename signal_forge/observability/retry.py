"""
Exponential backoff retry decorator with jitter for resilient network access.
"""

import functools
import random
import time
from typing import Any, Callable, Tuple, Type
from signal_forge.observability.logger import get_logger

logger = get_logger("retry")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
) -> Callable:
    """Decorator to retry function calls with exponential backoff and jitter."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            current_delay = base_delay

            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(
                            f"[{func.__name__}] Exceeded max retries ({max_retries}). Final exception: {e}"
                        )
                        raise

                    sleep_time = min(current_delay, max_delay)
                    if jitter:
                        sleep_time += random.uniform(0, 0.5 * sleep_time)

                    logger.warning(
                        f"[{func.__name__}] Attempt {attempt}/{max_retries} failed ({type(e).__name__}: {e}). "
                        f"Retrying in {sleep_time:.2f}s..."
                    )
                    time.sleep(sleep_time)
                    current_delay *= backoff_factor

        return wrapper
    return decorator
