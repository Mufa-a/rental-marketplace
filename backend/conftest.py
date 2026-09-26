import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """
    DRF throttling keys live in the cache, which persists across test
    functions (unlike the DB, which pytest-django rolls back per test).
    Without this, an OTP-throttle test can silently rate-limit a later,
    unrelated test using the same phone number.
    """
    cache.clear()
    yield
    cache.clear()
