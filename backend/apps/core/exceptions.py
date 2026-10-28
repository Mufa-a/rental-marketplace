"""
Normalizes every DRF error response into the shape documented in
docs/rental-marketplace-documentation.md section 13:
    {"error": {"code": ..., "message": ...}}
so the frontend never has to branch on which endpoint failed.
"""
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    """409 for requests that clash with existing state (duplicates, already-processed actions)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "This request conflicts with the current state."
    default_code = "conflict"


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(response.data, dict) and "error" not in response.data:
        if "detail" in response.data:
            message = str(response.data["detail"])
        else:
            first_field, first_errors = next(iter(response.data.items()))
            first = first_errors[0] if isinstance(first_errors, list) and first_errors else first_errors
            message = str(first) if first_field == "non_field_errors" else f"{first_field}: {first}"
        code = getattr(exc, "default_code", "request_error")
        if hasattr(exc, "get_codes"):
            codes = exc.get_codes()
            if isinstance(codes, str):
                code = codes
            elif isinstance(codes, list) and codes and isinstance(codes[0], str):
                code = codes[0]
        response.data = {
            "error": {
                "code": code,
                "message": message,
            }
        }
    elif isinstance(response.data, list) and response.data:
        response.data = {"error": {"code": getattr(exc, "default_code", "request_error"), "message": str(response.data[0])}}

    return response
