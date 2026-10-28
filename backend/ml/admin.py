from django.contrib import admin

from .models import ModelActivationLog, ModelVersion, TrainingDataset, TrainingRun

admin.site.register(ModelVersion)


@admin.register(TrainingRun)
class TrainingRunAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "requested_by", "created_at", "finished_at", "version"]
    list_filter = ["status"]


@admin.register(TrainingDataset)
class TrainingDatasetAdmin(admin.ModelAdmin):
    list_display = ["id", "filename", "source", "status", "rows", "uploaded_by", "created_at"]
    exclude = ["content"]


@admin.register(ModelActivationLog)
class ModelActivationLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "action", "previous_label", "new_label", "performed_by"]
