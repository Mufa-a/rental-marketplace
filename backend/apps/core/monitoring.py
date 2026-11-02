"""Optional Sentry error monitoring that never ships personal data.

Enabled only when SENTRY_DSN is set. No user identity, request bodies (OTP codes, phone numbers),
cookies, query strings (search filters, coordinates) or auth headers leave the server.
"""
SENSITIVE_HEADERS = {"authorization", "cookie", "x-internal-token"}


def scrub_event(event, hint=None):
    request = event.get("request") or {}
    for key in ("data", "cookies"):
        request.pop(key, None)
    if "query_string" in request:
        request["query_string"] = "[removed]"
    headers = request.get("headers") or {}
    for name in list(headers):
        if name.lower() in SENSITIVE_HEADERS:
            headers[name] = "[removed]"
    event.pop("user", None)
    return event


def init_sentry(dsn, *, environment, traces_sample_rate):
    import sentry_sdk

    sentry_sdk.init(dsn=dsn, send_default_pii=False, before_send=scrub_event, max_request_body_size="never",
                    environment=environment, traces_sample_rate=traces_sample_rate)
