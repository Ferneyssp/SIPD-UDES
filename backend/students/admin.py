from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("anonymous_code", "program", "semester", "academic_status", "is_active")
    list_filter = ("program", "academic_status", "is_active")
    search_fields = ("anonymous_code",)
