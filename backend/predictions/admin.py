from django.contrib import admin

from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("student", "academic_period", "probability", "risk_level", "status", "model_name", "prediction_date")
    list_filter = ("risk_level", "status", "academic_period")
    search_fields = ("student__anonymous_code",)
