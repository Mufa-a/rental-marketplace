from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Liveness/readiness probe for load balancers and Docker. Reveals no configuration."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
