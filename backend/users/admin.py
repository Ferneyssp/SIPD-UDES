from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class SipdUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("SIPD", {"fields": ("role", "programs", "can_manage_users")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("SIPD", {"fields": ("email", "role")}),)
    filter_horizontal = ("programs", "groups", "user_permissions")
