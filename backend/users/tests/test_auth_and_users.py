import time

from django.test import override_settings
from rest_framework.test import APIClient

from audit.models import AuditAction, AuditLog
from audit.services import client_ip
from config.testing import PASSWORD, SipdAPITestCase
from users.models import Role, User
from users.tokens import REFRESH_COOKIE

XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def login(username="admin_t", password=PASSWORD, remember=False):
    client = APIClient()
    response = client.post("/api/auth/login/", {"username": username, "password": password, "remember": remember},
                           format="json")
    return client, response


class LoginTests(SipdAPITestCase):
    def test_login_returns_access_and_sets_httponly_refresh_cookie(self):
        _, response = login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)  # el refresh token nunca va en el cuerpo
        cookie = response.cookies[REFRESH_COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/auth/")
        self.assertEqual(cookie["max-age"], "")  # sin "recordar": cookie de sesión
        self.assertEqual(response.data["user"]["role"], Role.ADMIN)
        self.assertNotIn("password", response.data["user"])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.LOGIN, user=self.admin).exists())

    def test_remember_makes_cookie_persistent(self):
        _, response = login(remember=True)
        self.assertNotEqual(response.cookies[REFRESH_COOKIE]["max-age"], "")

    def test_login_with_email(self):
        _, response = login("SIS@test.local")
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_is_rejected(self):
        _, response = login(password="incorrecta")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Credenciales incorrectas.")
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).exists())

    def test_inactive_user_cannot_login(self):
        User.objects.filter(pk=self.coordinator_sis.pk).update(is_active=False)
        _, response = login("coord_sis")
        self.assertEqual(response.status_code, 401)
        self.assertIn("desactivado", response.data["detail"])

    def test_protected_endpoint_requires_token(self):
        self.assertEqual(APIClient().get("/api/students/").status_code, 401)

    def test_refresh_uses_cookie_and_requires_csrf_header(self):
        client, response = login()
        self.assertEqual(client.post("/api/auth/refresh/").status_code, 403)  # sin cabecera anti-CSRF
        refreshed = client.post("/api/auth/refresh/", **XHR)
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn("access", refreshed.data)
        self.assertNotEqual(refreshed.cookies[REFRESH_COOKIE].value, response.cookies[REFRESH_COOKIE].value)  # rotación
        self.assertEqual(APIClient().post("/api/auth/refresh/", **XHR).status_code, 401)  # sin cookie

    def test_logout_blacklists_cookie_refresh(self):
        client, response = login()
        old_refresh = response.cookies[REFRESH_COOKIE].value
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        self.assertEqual(client.get("/api/auth/me/").data["username"], "admin_t")
        logout = client.post("/api/auth/logout/", **XHR)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.cookies[REFRESH_COOKIE].value, "")
        other = APIClient()
        other.cookies[REFRESH_COOKIE] = old_refresh
        self.assertEqual(other.post("/api/auth/refresh/", **XHR).status_code, 401)

    def test_passwords_are_hashed(self):
        self.assertNotEqual(self.admin.password, PASSWORD)
        self.assertTrue(self.admin.password.startswith("pbkdf2_"))

    def test_change_password_revokes_existing_sessions(self):
        client, response = login("coord_sis")
        old_refresh = response.cookies[REFRESH_COOKIE].value
        stolen = APIClient()
        stolen.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        time.sleep(1.05)  # el cambio debe ocurrir en un segundo posterior a la emisión del token (iat)
        changed = client.post("/api/auth/change-password/", {
            "current_password": PASSWORD, "new_password": "OtraClave#2026x", "confirm_password": "OtraClave#2026x",
        }, format="json")
        self.assertEqual(changed.status_code, 200)
        self.coordinator_sis.refresh_from_db()
        self.assertTrue(self.coordinator_sis.check_password("OtraClave#2026x"))
        self.assertIsNotNone(self.coordinator_sis.password_changed_at)
        # El access token anterior y el refresh token anterior dejan de funcionar.
        self.assertEqual(stolen.get("/api/auth/me/").status_code, 401)
        replay = APIClient()
        replay.cookies[REFRESH_COOKIE] = old_refresh
        self.assertEqual(replay.post("/api/auth/refresh/", **XHR).status_code, 401)
        # Con la nueva contraseña se inicia sesión con normalidad.
        _, fresh = login("coord_sis", "OtraClave#2026x")
        self.assertEqual(fresh.status_code, 200)


class UserManagementPermissionTests(SipdAPITestCase):
    def test_only_admin_lists_users(self):
        self.assertEqual(self.client_for(self.admin).get("/api/users/").status_code, 200)
        self.assertEqual(self.client_for(self.coordinator_sis).get("/api/users/").status_code, 403)
        self.assertEqual(self.client_for(self.coordinator).get("/api/users/").status_code, 403)

    def test_admin_creates_user_with_role_and_programs(self):
        response = self.client_for(self.admin).post("/api/users/", {
            "username": "nuevo", "email": "nuevo@test.local", "password": "ClaveNueva#2026",
            "role": Role.COORDINATOR, "program_ids": [self.sis.id],
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(username="nuevo")
        self.assertTrue(user.check_password("ClaveNueva#2026"))
        self.assertEqual(list(user.programs.all()), [self.sis])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.USER_CREATED).exists())

    def test_professor_role_no_longer_exists(self):
        response = self.client_for(self.admin).post("/api/users/", {
            "username": "prof", "email": "prof@test.local", "password": "ClaveNueva#2026", "role": "PROFESSOR",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(Role.values), {Role.ADMIN, Role.COORDINATOR})

    def test_weak_password_rejected(self):
        response = self.client_for(self.admin).post("/api/users/", {
            "username": "debil", "email": "debil@test.local", "password": "12345678", "role": Role.COORDINATOR,
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_delete_deactivates_instead_of_removing(self):
        response = self.client_for(self.admin).delete(f"/api/users/{self.coordinator_sis.id}/")
        self.assertEqual(response.status_code, 200)
        self.coordinator_sis.refresh_from_db()
        self.assertFalse(self.coordinator_sis.is_active)

    def test_admin_cannot_deactivate_self_or_change_own_role(self):
        client = self.client_for(self.admin)
        self.assertEqual(client.delete(f"/api/users/{self.admin.id}/").status_code, 400)
        self.assertEqual(client.patch(f"/api/users/{self.admin.id}/", {"role": Role.COORDINATOR}, format="json").status_code, 400)


class PrivilegeEscalationTests(SipdAPITestCase):
    """S1: un coordinador con permiso de gestión no puede escalar privilegios."""

    def setUp(self):
        super().setUp()
        User.objects.filter(pk=self.coordinator.pk).update(can_manage_users=True)
        self.coordinator.refresh_from_db()
        self.manager = self.client_for(self.coordinator)
        self.base = {"email": "x@test.local", "password": "ClaveNueva#2026", "program_ids": [self.sis.id]}

    def test_manager_can_create_coordinator_within_own_programs(self):
        response = self.manager.post("/api/users/", {**self.base, "username": "c1", "role": Role.COORDINATOR}, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_manager_cannot_create_admin(self):
        response = self.manager.post("/api/users/", {**self.base, "username": "a1", "role": Role.ADMIN}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="a1").exists())

    def test_manager_cannot_grant_user_management(self):
        response = self.manager.post("/api/users/", {**self.base, "username": "c2", "role": Role.COORDINATOR,
                                                     "can_manage_users": True}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_manager_cannot_assign_programs_outside_scope(self):
        other = self.civ.__class__.objects.create(code="IND", name="Industrial")
        response = self.manager.post("/api/users/", {**self.base, "username": "c3", "role": Role.COORDINATOR,
                                                     "program_ids": [other.id]}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_manager_cannot_change_own_role_or_edit_admins(self):
        self.assertEqual(self.manager.patch(f"/api/users/{self.coordinator.id}/", {"role": Role.ADMIN}, format="json").status_code, 404)
        self.assertEqual(self.manager.patch(f"/api/users/{self.admin.id}/", {"password": "Robada#2026xx"}, format="json").status_code, 404)
        self.assertEqual(self.manager.post(f"/api/users/{self.admin.id}/activate/").status_code, 404)
        self.assertEqual(self.manager.delete(f"/api/users/{self.admin.id}/").status_code, 404)
        self.coordinator.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertEqual(self.coordinator.role, Role.COORDINATOR)
        self.assertTrue(self.admin.check_password(PASSWORD))

    def test_manager_cannot_promote_a_coordinator(self):
        response = self.manager.patch(f"/api/users/{self.coordinator_sis.id}/", {"role": Role.ADMIN}, format="json")
        self.assertEqual(response.status_code, 400)
        self.coordinator_sis.refresh_from_db()
        self.assertEqual(self.coordinator_sis.role, Role.COORDINATOR)

    def test_manager_does_not_see_admins(self):
        usernames = {u["username"] for u in self.manager.get("/api/users/").data["results"]}
        self.assertNotIn(self.admin.username, usernames)
        self.assertNotIn(self.coordinator.username, usernames)
        self.assertIn(self.coordinator_sis.username, usernames)


class ClientIpTests(SipdAPITestCase):
    """S5: X-Forwarded-For sólo cuenta con proxies de confianza configurados."""

    def _request(self, forwarded):
        from django.test import RequestFactory

        return RequestFactory().get("/", HTTP_X_FORWARDED_FOR=forwarded, REMOTE_ADDR="10.0.0.5")

    @override_settings(TRUSTED_PROXY_COUNT=0)
    def test_forwarded_header_ignored_without_trusted_proxy(self):
        self.assertEqual(client_ip(self._request("1.2.3.4")), "10.0.0.5")

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_uses_entry_added_by_trusted_proxy(self):
        # El cliente inventa "1.2.3.4"; el proxy de confianza agrega la IP real al final.
        self.assertEqual(client_ip(self._request("1.2.3.4, 203.0.113.9")), "203.0.113.9")
