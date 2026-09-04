"""Polite request pacer module for rate limiting and human-like crawling.

Applies stochastic delay with uniform jitter between consecutive external HTTP requests
to prevent server degradation, IP bans, or rate-limit throttling (HTTP 429).
"""

import random
import time
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestPacer:
    """Manages polite pacing and jittered pauses between external requests."""

    def __init__(
        self,
        base_delay: Optional[float] = None,
        jitter_range: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Initializes the RequestPacer.

        Args:
            base_delay (Optional[float]): Base minimum delay in seconds.
            jitter_range (Optional[float]): Maximum random jitter added to base delay.
            enabled (Optional[bool]): Whether pacing is active.
        """
        self.base_delay = (
            base_delay if base_delay is not None else settings.ETL_REQUEST_DELAY_BASE
        )
        self.jitter_range = (
            jitter_range
            if jitter_range is not None
            else settings.ETL_REQUEST_DELAY_JITTER
        )
        self.enabled = (
            enabled if enabled is not None else settings.ETL_POLITE_PACING_ENABLED
        )
        self._last_request_time: float = 0.0

    def pace(self, target_label: str = "external source") -> float:
        """Enforces a polite, human-like delay before proceeding with the next request.

        Args:
            target_label (str): Descriptive label of the destination server for logging.

        Returns:
            float: Number of seconds slept (0.0 if disabled or elapsed > target).
        """
        if not self.enabled:
            return 0.0

        now = time.time()
        # If this is the very first request, record timestamp and proceed without delay
        if self._last_request_time <= 0.0:
            self._last_request_time = now
            return 0.0

        elapsed = now - self._last_request_time
        # Desired delay = base_delay + uniform(0, jitter_range)
        desired_delay = self.base_delay + random.uniform(0.0, max(0.0, self.jitter_range))
        wait_time = desired_delay - elapsed

        if wait_time > 0.0:
            logger.info(
                "Human-like pacing: waiting %.2fs before requesting %s...",
                wait_time,
                target_label,
            )
            time.sleep(wait_time)
            slept = wait_time
        else:
            slept = 0.0

        self._last_request_time = time.time()
        return slept
