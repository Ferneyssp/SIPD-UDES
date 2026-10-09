"""Configuración pública (para usuarios autenticados) que consume el frontend.
Así los umbrales y catálogos NO se duplican en React."""
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from academic.models import AcademicPeriod
from followups.models import FollowUpStatus, InterventionType
from students.models import AcademicStatus
from students.queries import NO_FOLLOWUP
from users.models import Role

from .risk import get_thresholds, risk_levels_description


def _choices(enum):
    return [{"value": value, "label": label} for value, label in enum.choices]


class SystemConfigView(APIView):
    def get(self, request):
        from sipd_ml.config import FEATURE_LABELS

        current = AcademicPeriod.get_current()
        return Response({
            "risk_thresholds": get_thresholds(),
            "risk_levels": risk_levels_description(),
            "gpa_range": {"min": settings.GPA_MIN, "max": settings.GPA_MAX},
            "current_period": current.code if current else None,
            "roles": _choices(Role),
            "academic_statuses": _choices(AcademicStatus),
            "followup_statuses": _choices(FollowUpStatus) + [{"value": NO_FOLLOWUP, "label": "Sin seguimiento"}],
            "intervention_types": _choices(InterventionType),
            "feature_labels": FEATURE_LABELS,
            "upload_max_mb": settings.UPLOAD_MAX_BYTES // (1024 * 1024),
        })


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})
