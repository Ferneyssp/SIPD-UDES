from rest_framework import serializers

from .models import ModelActivationLog, ModelVersion, TrainingDataset, TrainingRun


class ModelVersionSerializer(serializers.ModelSerializer):
    approval_status_display = serializers.CharField(source="get_approval_status_display", read_only=True)
    approved_by = serializers.CharField(source="approved_by.username", read_only=True, allow_null=True)
    can_be_activated = serializers.BooleanField(read_only=True)

    class Meta:
        model = ModelVersion
        fields = ["id", "name", "algorithm", "version", "metrics", "trained_at", "active", "is_synthetic",
                  "selection_metric", "artifact_dir", "selected", "dataset_rows", "evaluation", "training_run",
                  "approval_status", "approval_status_display", "acceptance", "approved_by", "approved_at",
                  "approval_notes", "can_be_activated"]


class TrainingDatasetSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source="uploaded_by.username", read_only=True, allow_null=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TrainingDataset
        fields = ["id", "source", "source_display", "filename", "checksum", "size_bytes", "rows", "status",
                  "status_display", "report", "is_synthetic", "uploaded_by", "created_at"]


class TrainingRunSerializer(serializers.ModelSerializer):
    requested_by = serializers.CharField(source="requested_by.username", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    dataset = TrainingDatasetSerializer(read_only=True)
    is_finished = serializers.BooleanField(read_only=True)
    versions = serializers.SerializerMethodField()

    class Meta:
        model = TrainingRun
        fields = ["id", "status", "status_display", "stage_message", "events", "algorithms", "selection_metric",
                  "threshold", "version", "selected_algorithm", "ranking", "error_message", "requested_by", "dataset",
                  "created_at", "started_at", "finished_at", "heartbeat_at", "is_finished", "versions"]

    def get_versions(self, run):
        versions = sorted(run.model_versions.all(), key=lambda v: (not v.selected, v.algorithm))
        return [{"id": v.id, "name": v.name, "algorithm": v.algorithm, "version": v.version, "selected": v.selected,
                 "active": v.active, "approval_status": v.approval_status,
                 "approval_status_display": v.get_approval_status_display(), "metrics": v.metrics,
                 "acceptance": v.acceptance, "acceptance_passed": v.acceptance.get("passed")} for v in versions]


class TrainingRunListSerializer(TrainingRunSerializer):
    dataset = serializers.SerializerMethodField()

    class Meta(TrainingRunSerializer.Meta):
        fields = [f for f in TrainingRunSerializer.Meta.fields if f not in {"events", "ranking"}]

    def get_dataset(self, run):
        return {"id": run.dataset_id, "filename": run.dataset.filename, "rows": run.dataset.rows,
                "source": run.dataset.source, "is_synthetic": run.dataset.is_synthetic}


class StartRunSerializer(serializers.Serializer):
    dataset = serializers.PrimaryKeyRelatedField(queryset=TrainingDataset.objects.all())
    algorithms = serializers.ListField(child=serializers.CharField(max_length=40), allow_empty=False, max_length=10)
    selection_metric = serializers.CharField(max_length=20)
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("Debe confirmar explícitamente el inicio del entrenamiento.")
        return value


class ReviewSerializer(serializers.Serializer):
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ActivationLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    performed_by = serializers.CharField(source="performed_by.username", read_only=True, allow_null=True)

    class Meta:
        model = ModelActivationLog
        fields = ["id", "action", "action_display", "previous_version", "previous_label", "new_version", "new_label",
                  "performed_by", "created_at"]
