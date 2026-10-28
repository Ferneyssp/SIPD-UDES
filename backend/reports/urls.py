from django.urls import path

from . import views

urlpatterns = [
    path("risk/", views.RiskReportView.as_view(), name="report-risk"),
    path("risk/csv/", views.RiskReportCsvView.as_view(), name="report-risk-csv"),
    path("risk/pdf/", views.RiskReportPdfView.as_view(), name="report-risk-pdf"),
    path("risk/students/csv/", views.RiskStudentsCsvView.as_view(), name="report-risk-students-csv"),
    path("models/", views.ModelReportView.as_view(), name="report-models"),
    path("models/csv/", views.ModelReportCsvView.as_view(), name="report-models-csv"),
    path("models/pdf/", views.ModelReportPdfView.as_view(), name="report-models-pdf"),
    path("activity/", views.ActivityReportView.as_view(), name="report-activity"),
    path("activity/csv/", views.ActivityReportCsvView.as_view(), name="report-activity-csv"),
    path("activity/pdf/", views.ActivityReportPdfView.as_view(), name="report-activity-pdf"),
]
