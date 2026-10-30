from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from alerts.views import AlertViewSet
from academic.views import AcademicPeriodViewSet, ProgramViewSet
from followups.views import FollowUpViewSet, ResponsibleUsersView
from ml.views import ModelVersionViewSet, TrainingDatasetViewSet, TrainingOverviewView, TrainingRunViewSet
from notifications.views import NotificationViewSet
from predictions.views import PredictionViewSet
from students.views import StudentViewSet
from uploads.views import DataUploadViewSet
from users.password_reset import PasswordResetConfirmView, PasswordResetRequestView
from users.views import ChangePasswordView, CookieTokenRefreshView, LoginView, LogoutView, MeView, UserViewSet

from .views import HealthView, SystemConfigView

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("programs", ProgramViewSet, basename="program")
router.register("periods", AcademicPeriodViewSet, basename="period")
router.register("students", StudentViewSet, basename="student")
router.register("predictions", PredictionViewSet, basename="prediction")
router.register("models", ModelVersionViewSet, basename="model-version")
router.register("uploads", DataUploadViewSet, basename="upload")
router.register("followups", FollowUpViewSet, basename="followup")
router.register("training/datasets", TrainingDatasetViewSet, basename="training-dataset")
router.register("training/runs", TrainingRunViewSet, basename="training-run")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("alerts", AlertViewSet, basename="alert")

auth_patterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", CookieTokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include(auth_patterns)),
    path("api/config/", SystemConfigView.as_view(), name="system-config"),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/followups/responsibles/", ResponsibleUsersView.as_view(), name="followup-responsibles"),
    path("api/training/overview/", TrainingOverviewView.as_view(), name="training-overview"),
    path("api/reports/", include("reports.urls")),
    path("api/", include(router.urls)),
]
