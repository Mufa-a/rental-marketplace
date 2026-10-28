from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.core.permissions import is_platform_admin


def can_manage(user, property):
    return bool(user and user.is_authenticated and (is_platform_admin(user) or property.landlord.user_id == user.id))


class IsLandlordOrAdmin(BasePermission):
    message = "Only landlords can manage listings."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.role == User.Role.LANDLORD or is_platform_admin(user)))
