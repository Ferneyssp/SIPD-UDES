"""
Reportes (consulta, CSV y PDF). Cada exportación usa la misma función de cálculo que la
vista en pantalla, con los mismos filtros, y queda registrada en auditoría.

Permisos:
  - Riesgo estudiantil agregado: todos los roles, limitado a su ámbito de programas.
  - Listado individual (CSV): sólo Administrador.
  - Evaluación de modelos: todos los roles (sin datos personales).
  - Actividad administrativa: sólo Administrador.
"""
from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditAction
from audit.services import log_action
from users.permissions import IsAdminRole

from . import exporters, services


def _filename(prefix: str, extension: str) -> str:
    return f"sipd_{prefix}_{timezone.localtime():%Y%m%d_%H%M}.{extension}"


def _log_export(request, report: str, file_format: str, filters: dict):
    log_action(AuditAction.REPORT_EXPORTED, request=request, entity="Report", entity_id=report,
               description=f"Exportación {file_format.upper()} del reporte {report}",
               metadata={"format": file_format, "filters": {k: str(v) for k, v in filters.items() if v}})


def _csv_response(request, report: str, header, rows, filters):
    _log_export(request, report, "csv", filters)
    response = StreamingHttpResponse(exporters.csv_rows(header, rows), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename(report, "csv")}"'
    response["Cache-Control"] = "no-store"
    return response


def _pdf_response(request, report: str, content: bytes, filters):
    _log_export(request, report, "pdf", filters)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{_filename(report, "pdf")}"'
    response["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------------------- riesgo
RISK_GROUP_HEADER = [("group_type", "Agrupación"), ("group", "Grupo"), ("total", "Estudiantes"),
                     ("ALTO", "Riesgo alto"), ("ALTO_pct", "% alto"), ("MEDIO", "Riesgo medio"), ("MEDIO_pct", "% medio"),
                     ("BAJO", "Riesgo bajo"), ("BAJO_pct", "% bajo")]


def _risk_rows(report):
    levels = {item["code"]: item for item in report["totals"]["levels"]}
    yield {"group_type": "Total", "group": report["filters"]["period"] or "Todos los periodos",
           "total": report["totals"]["students"],
           **{code: levels[code]["count"] for code in levels}, **{f"{code}_pct": levels[code]["pct"] for code in levels}}
    for row in report["by_program"]:
        yield {"group_type": "Programa", "group": row["program"], **row}
    for row in report["by_semester"]:
        yield {"group_type": "Semestre", "group": row["semester"], **row}


class RiskReportView(APIView):
    def get(self, request):
        return Response(services.risk_report(request.user, request.query_params))


class RiskReportCsvView(APIView):
    def get(self, request):
        report = services.risk_report(request.user, request.query_params)
        return _csv_response(request, "riesgo", RISK_GROUP_HEADER, _risk_rows(report), report["filters"])


class RiskReportPdfView(APIView):
    def get(self, request):
        report = services.risk_report(request.user, request.query_params)
        return _pdf_response(request, "riesgo", exporters.risk_pdf(report), report["filters"])


class RiskStudentsCsvView(APIView):
    """Listado individual: requiere rol Administrador (autorización explícita)."""

    permission_classes = [IsAdminRole]
    header = [("student_code", "Código seudonimizado"), ("program", "Programa"), ("semester", "Semestre"),
              ("period", "Periodo"), ("probability", "Probabilidad estimada"), ("risk_level", "Nivel de riesgo estimado"),
              ("model", "Modelo"), ("model_version", "Versión del modelo"), ("prediction_date", "Fecha de predicción")]

    def get(self, request):
        filters = services.risk_filters(request.query_params)
        rows = services.risk_student_rows(request.user, request.query_params, settings.REPORT_EXPORT_MAX_ROWS)
        return _csv_response(request, "riesgo_individual", self.header, rows, filters)


# ---------------------------------------------------------------------------- modelos
class ModelReportView(APIView):
    def get(self, request):
        return Response(services.model_report(request.user, request.query_params))


class ModelReportCsvView(APIView):
    header = [("name", "Modelo"), ("algorithm", "Algoritmo"), ("version", "Versión"), ("trained_at", "Fecha de entrenamiento"),
              ("dataset_rows", "Registros del dataset"), ("train_size", "Registros de entrenamiento"),
              ("test_size", "Registros de prueba"), ("threshold", "Umbral de evaluación"), ("accuracy", "Accuracy (prueba)"),
              ("precision", "Precision (prueba)"), ("recall", "Recall (prueba)"), ("f1", "F1 (prueba)"),
              ("roc_auc", "ROC-AUC (prueba)"), ("tn", "VN"), ("fp", "FP"), ("fn", "FN"), ("tp", "VP"),
              ("approval_status_display", "Aprobación"), ("active", "Activo"), ("is_synthetic", "Datos sintéticos"),
              ("comparison_group", "Grupo de evaluación")]

    def get(self, request):
        report = services.model_report(request.user, request.query_params)
        rows = ({**v, **v["metrics"], **(v["confusion_matrix"] or {})} for v in report["versions"])
        return _csv_response(request, "modelos", self.header, rows, report["filters"])


class ModelReportPdfView(APIView):
    def get(self, request):
        report = services.model_report(request.user, request.query_params)
        return _pdf_response(request, "modelos", exporters.model_pdf(report), report["filters"])


# ---------------------------------------------------------------------------- actividad
class ActivityReportView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(services.activity_report(request.query_params))


class ActivityReportCsvView(APIView):
    permission_classes = [IsAdminRole]
    header = [("kind", "Tipo"), ("date", "Fecha"), ("detail", "Detalle"), ("status", "Estado"), ("user", "Usuario"),
              ("error", "Error")]

    def get(self, request):
        report = services.activity_report(request.query_params)

        def rows():
            for run in report["training"]["runs"]:
                yield {"kind": f"Reentrenamiento #{run['id']}", "date": run["created_at"],
                       "detail": f"{run['dataset']} ({run['rows']} registros) · {', '.join(run['algorithms'])}"
                                 + (f" · versión {run['version']}" if run["version"] else ""),
                       "status": run["status_display"], "user": run["requested_by"], "error": run["error"]}
            for item in report["activations"]:
                yield {"kind": item["action_display"], "date": item["created_at"],
                       "detail": f"{item['previous'] or '—'} → {item['new']}", "status": "Registrado",
                       "user": item["performed_by"], "error": ""}

        return _csv_response(request, "actividad", self.header, rows(), report["filters"])


class ActivityReportPdfView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        report = services.activity_report(request.query_params)
        return _pdf_response(request, "actividad", exporters.activity_pdf(report), report["filters"])
