import hmac

from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle


def is_internal_render(request):
    """True for server-side renders from our own Next.js server (shared secret header, never sent by browsers)."""
    token = settings.INTERNAL_API_TOKEN
    supplied = request.headers.get("X-Internal-Token", "")
    return bool(token) and hmac.compare_digest(supplied.encode(), token.encode())


class PublicScopedRateThrottle(ScopedRateThrottle):
    """Per-IP limits for public endpoints, except for our own SSR server, which renders for every visitor
    from a single IP and is itself cached."""

    def allow_request(self, request, view):
        return True if is_internal_render(request) else super().allow_request(request, view)
