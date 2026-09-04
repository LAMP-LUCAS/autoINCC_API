"""Unit tests for RequestPacer rate limiting and jitter calculation."""

import time
import pytest
from app.etl.pacing import RequestPacer


def test_request_pacer_first_call_no_delay() -> None:
    """Verifies that the first call to pace does not block."""
    pacer = RequestPacer(base_delay=1.0, jitter_range=0.5, enabled=True)
    start = time.time()
    slept = pacer.pace(target_label="test_source")
    elapsed = time.time() - start

    assert slept == 0.0
    assert elapsed < 0.1


def test_request_pacer_subsequent_call_applies_delay() -> None:
    """Verifies that a subsequent call within the window applies a delay with jitter."""
    base_delay = 0.15
    jitter_range = 0.05
    pacer = RequestPacer(base_delay=base_delay, jitter_range=jitter_range, enabled=True)

    # First call sets anchor timestamp
    pacer.pace("first_call")

    start = time.time()
    slept = pacer.pace("second_call")
    elapsed = time.time() - start

    assert slept >= (base_delay - 0.05)
    assert elapsed >= (base_delay - 0.05)
    assert elapsed <= (base_delay + jitter_range + 0.1)


def test_request_pacer_disabled() -> None:
    """Verifies that when disabled, pace returns immediately without sleeping."""
    pacer = RequestPacer(base_delay=5.0, jitter_range=5.0, enabled=False)
    start = time.time()
    slept = pacer.pace("disabled_call")
    slept2 = pacer.pace("disabled_call_2")
    elapsed = time.time() - start

    assert slept == 0.0
    assert slept2 == 0.0
    assert elapsed < 0.05
