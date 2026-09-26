import re

from rest_framework.throttling import SimpleRateThrottle

from .serializers import normalize_phone

_RATE_RE = re.compile(r"^(\d*)([smhd])")


class PhoneOTPThrottle(SimpleRateThrottle):
    """
    Rate-limits OTP requests per phone number, not per IP/user. The phone
    number is the actual abuse surface here — SMS cost and brute-force
    risk both key off it, and an attacker can trivially rotate IPs but
    not phone numbers. Scope/rate ('otp_request': '3/15min') comes from
    REST_FRAMEWORK.DEFAULT_THROTTLE_RATES in settings.

    DRF's stock SimpleRateThrottle.parse_rate only reads the period's
    first character (so '3/m' works but '3/15min' raises KeyError on
    '1') — overridden here to support a real multi-minute window instead
    of rounding our 15-minute design decision down to "3 per minute".
    """

    scope = "otp_request"

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        num, period = rate.split("/")
        match = _RATE_RE.match(period)
        if not match:
            raise ValueError(f"Invalid throttle rate period: {period!r}")
        multiplier_str, unit = match.groups()
        multiplier = int(multiplier_str) if multiplier_str else 1
        duration = multiplier * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        return int(num), duration

    def get_cache_key(self, request, view):
        phone = request.data.get("phone_number")
        if not phone:
            return None
        try:
            phone = normalize_phone(phone)
        except (AttributeError, TypeError):
            return None
        return self.cache_format % {"scope": self.scope, "ident": phone}
