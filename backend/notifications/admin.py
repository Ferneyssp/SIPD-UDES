from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "recipient", "type", "level", "title", "read_at"]
    list_filter = ["type", "level"]
    readonly_fields = [f.name for f in Notification._meta.fields]
