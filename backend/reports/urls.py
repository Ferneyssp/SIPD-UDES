from django.urls import path

from . import views

urlpatterns = [
    path("risk/", views.RiskReportView.as_view(), name="report-risk"),
    path("risk/csv/", views.RiskReportCsvView.as_view(), name="report-risk-csv"),
    path("risk/pdf/", views.RiskReportPdfView.as_view(), name="report-risk-pdf"),
    path("risk/students/csv/", views.RiskStudentsCsvView.as_view(), name="report-risk-students-csv"),
]
