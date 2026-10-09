"""Permisos por rol."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role


class IsAdminRole(BasePermission):
    message = "Esta acción requiere rol de Administrador."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.ADMIN)


class CanManageUsers(BasePermission):
    message = "No tiene permiso para administrar usuarios."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.can_manage_users_effective)


class IsAdminOrReadOnly(BasePermission):
    message = "Sólo el Administrador puede modificar esta información."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or request.user.role == Role.ADMIN


class CanRegisterFollowUp(BasePermission):
    """Profesores, coordinadores y administradores pueden registrar seguimiento."""

    message = "No tiene permiso para registrar seguimiento."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in Role.values)
