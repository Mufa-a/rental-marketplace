from rest_framework.permissions import BasePermission

from apps.accounts.models import User


def can_manage(user, property):
    return bool(user and user.is_authenticated and (user.role == User.Role.ADMIN or property.landlord.user_id == user.id))


class IsLandlordOrAdmin(BasePermission):
    message = "Only landlords can manage listings."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in (User.Role.LANDLORD, User.Role.ADMIN))
