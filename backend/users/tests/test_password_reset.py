import re
import time

from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from audit.models import AuditAction, AuditLog
from config.testing import PASSWORD, SipdAPITestCase

LINK = re.compile(r"/restablecer-contrasena/(?P<uid>[^/\s]+)/(?P<token>[^/\s]+)")
NEW_PASSWORD = "Recuperada#2026x"


class PasswordResetTests(SipdAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()  # contadores del límite de solicitudes
        self.client = APIClient()

    def request_reset(self, email="sis@test.local"):
        return self.client.post("/api/auth/password-reset/", {"email": email}, format="json")

    def link_parts(self):
        return LINK.search(mail.outbox[-1].body).groupdict()

    def test_sends_single_use_link_and_changes_password(self):
        response = self.request_reset("SIS@test.local")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["sis@test.local"])
        self.assertIn("Restablecer contraseña", message.subject)
        self.assertIn("/restablecer-contrasena/", message.alternatives[0][0])  # versión HTML
        parts = self.link_parts()
        confirm = self.client.post("/api/auth/password-reset/confirm/", {
            **parts, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}, format="json")
        self.assertEqual(confirm.status_code, 200, confirm.data)
        self.coordinator_sis.refresh_from_db()
        self.assertTrue(self.coordinator_sis.check_password(NEW_PASSWORD))
        self.assertIsNotNone(self.coordinator_sis.password_changed_at)  # se cerraron las sesiones anteriores
        # El enlace es de un solo uso.
        again = self.client.post("/api/auth/password-reset/confirm/", {
            **parts, "new_password": "OtraMas#2026xx", "confirm_password": "OtraMas#2026xx"}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertIn("token", again.data["errors"])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PASSWORD_RESET_REQUESTED).exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PASSWORD_RESET).exists())

    def test_same_response_for_unknown_or_inactive_accounts(self):
        known = self.request_reset("sis@test.local").data["detail"]
        unknown = self.request_reset("nadie@test.local")
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.data["detail"], known)
        self.coordinator.is_active = False
        self.coordinator.save(update_fields=["is_active"])
        self.assertEqual(self.request_reset("coord@test.local").data["detail"], known)
        self.assertEqual(len(mail.outbox), 1)  # sólo la cuenta activa existente recibió correo

    def test_invalid_token_and_password_rules(self):
        self.request_reset()
        parts = self.link_parts()
        bad = self.client.post("/api/auth/password-reset/confirm/", {
            "uid": parts["uid"], "token": "falso-123", "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}, format="json")
        self.assertEqual(bad.status_code, 400)
        mismatch = self.client.post("/api/auth/password-reset/confirm/", {
            **parts, "new_password": NEW_PASSWORD, "confirm_password": "distinta#2026x"}, format="json")
        self.assertIn("confirm_password", mismatch.data["errors"])
        weak = self.client.post("/api/auth/password-reset/confirm/", {
            **parts, "new_password": "12345678", "confirm_password": "12345678"}, format="json")
        self.assertIn("new_password", weak.data["errors"])
        self.coordinator_sis.refresh_from_db()
        self.assertTrue(self.coordinator_sis.check_password(PASSWORD))  # nada cambió

    def test_link_expires(self):
        with self.settings(PASSWORD_RESET_TIMEOUT=0):
            self.request_reset()
            parts = self.link_parts()
            time.sleep(1.1)
            response = self.client.post("/api/auth/password-reset/confirm/", {
                **parts, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_requests_are_rate_limited(self):
        codes = [self.request_reset("nadie@test.local").status_code for _ in range(6)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertEqual(codes[5], 429)

    def test_vercel_without_smtp_does_not_leak_link_to_logs(self):
        with self.settings(ON_VERCEL=True, EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"), \
                self.assertLogs("users.password_reset", level="ERROR") as logs:
            response = self.request_reset("sis@test.local")
        self.assertEqual(response.status_code, 200)  # misma respuesta genérica
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("Correo no configurado", logs.output[0])
