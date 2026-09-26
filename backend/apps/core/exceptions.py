"""
Normalizes every DRF error response into the shape documented in
docs/rental-marketplace-documentation.md section 13:
    {"error": {"code": ..., "message": ...}}
so the frontend never has to branch on which endpoint failed.
"""
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(response.data, dict) and "error" not in response.data:
        if "detail" in response.data:
            message = str(response.data["detail"])
        else:
            first_field, first_errors = next(iter(response.data.items()))
            message = (
                f"{first_field}: {first_errors[0]}"
                if isinstance(first_errors, list)
                else str(first_errors)
            )
        response.data = {
            "error": {
                "code": getattr(exc, "default_code", "request_error"),
                "message": message,
            }
        }

    return response
