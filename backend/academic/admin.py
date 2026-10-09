from django.contrib import admin

from .models import AcademicPeriod, AcademicRecord, Program

admin.site.register(Program)
admin.site.register(AcademicPeriod)


@admin.register(AcademicRecord)
class AcademicRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "academic_period", "semester", "gpa", "attendance_percentage")
    list_filter = ("academic_period",)
    search_fields = ("student__anonymous_code",)
