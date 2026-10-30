from config.testing import SipdAPITestCase
from notifications.models import Notification, NotificationType
from notifications.services import notify


class NotificationApiTests(SipdAPITestCase):
    def setUp(self):
        super().setUp()
        with self.captureOnCommitCallbacks(execute=True):
            notify([self.admin], NotificationType.TRAINING_COMPLETED, "Entrenamiento listo", "Detalle", link="/reentrenamiento")
            notify([self.admin], NotificationType.DATASET_REJECTED, "Dataset rechazado")
            notify([self.coordinator_sis], NotificationType.PREDICTIONS_COMPLETED, "Nuevas predicciones")

    def test_each_user_only_sees_own_notifications(self):
        data = self.client_for(self.coordinator_sis).get("/api/notifications/").data
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["title"], "Nuevas predicciones")
        foreign = Notification.objects.filter(recipient=self.admin).first()
        client = self.client_for(self.coordinator_sis)
        self.assertEqual(client.get(f"/api/notifications/{foreign.pk}/").status_code, 404)
        self.assertEqual(client.post(f"/api/notifications/{foreign.pk}/read/").status_code, 404)
        self.assertIsNone(Notification.objects.get(pk=foreign.pk).read_at)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 401)

    def test_unread_count_mark_read_and_read_all(self):
        client = self.client_for(self.admin)
        self.assertEqual(client.get("/api/notifications/unread-count/").data["unread"], 2)
        target = Notification.objects.filter(recipient=self.admin).first()
        response = client.post(f"/api/notifications/{target.pk}/read/")
        self.assertTrue(response.data["is_read"])
        self.assertEqual(client.get("/api/notifications/unread-count/").data["unread"], 1)
        self.assertEqual(client.post("/api/notifications/read-all/").data["updated"], 1)
        self.assertEqual(client.get("/api/notifications/unread-count/").data["unread"], 0)
        # Leer no borra el historial.
        self.assertEqual(client.get("/api/notifications/").data["count"], 2)
        # Marcar todas no afecta a otros usuarios.
        self.assertEqual(self.client_for(self.coordinator_sis).get("/api/notifications/unread-count/").data["unread"], 1)

    def test_filters(self):
        client = self.client_for(self.admin)
        self.assertEqual(client.get("/api/notifications/?category=DATOS").data["count"], 1)
        self.assertEqual(client.get(f"/api/notifications/?type={NotificationType.TRAINING_COMPLETED}").data["count"], 1)
        client.post("/api/notifications/read-all/")
        self.assertEqual(client.get("/api/notifications/?is_read=false").data["count"], 0)
        self.assertEqual(client.get("/api/notifications/?is_read=true").data["count"], 2)

    def test_recipient_cannot_be_changed_by_client(self):
        client = self.client_for(self.coordinator_sis)
        self.assertEqual(client.post("/api/notifications/", {"recipient": self.admin.pk, "title": "x"}).status_code, 405)
        target = Notification.objects.get(recipient=self.coordinator_sis)
        self.assertEqual(client.patch(f"/api/notifications/{target.pk}/", {"recipient": self.admin.pk}).status_code, 405)

    def test_duplicate_events_are_not_repeated(self):
        for _ in range(3):
            with self.captureOnCommitCallbacks(execute=True):
                notify([self.admin], NotificationType.TRAINING_FAILED, "Fallo", dedupe_key="run-1-failed")
        self.assertEqual(Notification.objects.filter(type=NotificationType.TRAINING_FAILED).count(), 1)

    def test_external_links_are_discarded(self):
        with self.captureOnCommitCallbacks(execute=True):
            notify([self.admin], NotificationType.TRAINING_STARTED, "x", link="https://malicioso.example")
        self.assertEqual(Notification.objects.get(type=NotificationType.TRAINING_STARTED).link, "")

    def test_batch_predictions_notify_executor_and_users_in_scope(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.admin).post("/api/predictions/run-batch/", {"academic_period": "2026-2", "program": "CIV"},
                                             format="json")
        self.assertTrue(Notification.objects.filter(recipient=self.admin, type=NotificationType.PREDICTIONS_COMPLETED).exists())
        # El coordinador de SIS y CIV recibe el aviso; el coordinador sólo de SIS no recibe aviso de CIV.
        self.assertTrue(Notification.objects.filter(recipient=self.coordinator, type=NotificationType.PREDICTIONS_COMPLETED).exists())
        self.assertEqual(Notification.objects.filter(recipient=self.coordinator_sis, type=NotificationType.PREDICTIONS_COMPLETED).count(), 1)
