from rest_framework.test import APIClient

from audit.models import AuditAction, AuditLog
from config.testing import PASSWORD, SipdAPITestCase
from users.models import Role, User


class LoginTests(SipdAPITestCase):
    def test_login_with_username_returns_tokens_and_profile(self):
        response = APIClient().post("/api/auth/login/", {"username": "admin_t", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], Role.ADMIN)
        self.assertNotIn("password", response.data["user"])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.LOGIN, user=self.admin).exists())

    def test_login_with_email(self):
        response = APIClient().post("/api/auth/login/", {"username": "PROF@test.local", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_is_rejected(self):
        response = APIClient().post("/api/auth/login/", {"username": "admin_t", "password": "incorrecta"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Credenciales incorrectas.")
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED).exists())

    def test_inactive_user_cannot_login(self):
        User.objects.filter(pk=self.professor.pk).update(is_active=False)
        response = APIClient().post("/api/auth/login/", {"username": "prof_t", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertIn("desactivado", response.data["detail"])

    def test_protected_endpoint_requires_token(self):
        self.assertEqual(APIClient().get("/api/students/").status_code, 401)

    def test_jwt_access_and_logout_blacklists_refresh(self):
        client = APIClient()
        tokens = client.post("/api/auth/login/", {"username": "admin_t", "password": PASSWORD}, format="json").data
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(client.get("/api/auth/me/").data["username"], "admin_t")
        self.assertEqual(client.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json").status_code, 200)
        refresh = APIClient().post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)

    def test_passwords_are_hashed(self):
        self.assertNotEqual(self.admin.password, PASSWORD)
        self.assertTrue(self.admin.password.startswith("pbkdf2_"))

    def test_change_password(self):
        client = self.client_for(self.professor)
        response = client.post("/api/auth/change-password/", {
            "current_password": PASSWORD, "new_password": "OtraClave#2026x", "confirm_password": "OtraClave#2026x",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.professor.refresh_from_db()
        self.assertTrue(self.professor.check_password("OtraClave#2026x"))


class UserManagementPermissionTests(SipdAPITestCase):
    def test_only_admin_lists_users(self):
        self.assertEqual(self.client_for(self.admin).get("/api/users/").status_code, 200)
        self.assertEqual(self.client_for(self.professor).get("/api/users/").status_code, 403)
        self.assertEqual(self.client_for(self.coordinator).get("/api/users/").status_code, 403)

    def test_coordinator_with_explicit_permission_can_manage_users(self):
        User.objects.filter(pk=self.coordinator.pk).update(can_manage_users=True)
        self.coordinator.refresh_from_db()
        self.assertEqual(self.client_for(self.coordinator).get("/api/users/").status_code, 200)

    def test_admin_creates_user_with_role_and_programs(self):
        response = self.client_for(self.admin).post("/api/users/", {
            "username": "nuevo", "email": "nuevo@test.local", "password": "ClaveNueva#2026",
            "role": Role.PROFESSOR, "program_ids": [self.sis.id],
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(username="nuevo")
        self.assertTrue(user.check_password("ClaveNueva#2026"))
        self.assertEqual(list(user.programs.all()), [self.sis])
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.USER_CREATED).exists())

    def test_weak_password_rejected(self):
        response = self.client_for(self.admin).post("/api/users/", {
            "username": "debil", "email": "debil@test.local", "password": "12345678", "role": Role.PROFESSOR,
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_delete_deactivates_instead_of_removing(self):
        response = self.client_for(self.admin).delete(f"/api/users/{self.professor.id}/")
        self.assertEqual(response.status_code, 200)
        self.professor.refresh_from_db()
        self.assertFalse(self.professor.is_active)

    def test_admin_cannot_deactivate_self(self):
        self.assertEqual(self.client_for(self.admin).delete(f"/api/users/{self.admin.id}/").status_code, 400)
