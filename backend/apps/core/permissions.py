"""One definition of "platform administrator", enforced server-side everywhere.

An administrator is an active staff account with the admin role. Requiring both
means a role edit alone (or a stray is_staff flag) never grants cross-account
access; hiding buttons in the frontend is never the control.
"""
from rest_framework.permissions import BasePermission

from apps.accounts.models import User


def is_platform_admin(user) -> bool:
    return bool(
        user and user.is_authenticated and user.is_active
        and user.role == User.Role.ADMIN and user.is_staff
    )


class IsPlatformAdmin(BasePermission):
    message = "Admin access is required."

    def has_permission(self, request, view):
        return is_platform_admin(request.user)
