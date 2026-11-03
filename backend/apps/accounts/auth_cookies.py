"""The refresh token lives in an HttpOnly cookie, never in JavaScript-readable storage.

The cookie is scoped to the auth endpoints (so it is not sent with every API call), SameSite=Strict
(so other sites cannot make the browser use it), and Secure in production. The short-lived access
token is returned in the response body and kept only in the page's memory.
"""
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken


def _options():
    cfg = settings.REFRESH_COOKIE
    return {"path": cfg["path"], "samesite": cfg["samesite"], "domain": cfg.get("domain") or None}


def set_refresh_cookie(response, refresh):
    lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    response.set_cookie(settings.REFRESH_COOKIE["name"], str(refresh), max_age=lifetime, httponly=True,
                        secure=settings.REFRESH_COOKIE["secure"], **_options())
    return response


def clear_refresh_cookie(response):
    response.delete_cookie(settings.REFRESH_COOKIE["name"], **_options())
    return response


def read_refresh(request):
    """Cookie first; a body field is accepted for non-browser API clients."""
    return request.COOKIES.get(settings.REFRESH_COOKIE["name"]) or (request.data.get("refresh") if hasattr(request, "data") else None)


def issue_session(response, user):
    """Attach a fresh token pair: access in the body, refresh in the cookie."""
    refresh = RefreshToken.for_user(user)
    response.data["access"] = str(refresh.access_token)
    response.data["user"] = {"id": user.id, "phone_number": user.phone_number, "role": user.role}
    return set_refresh_cookie(response, refresh)
