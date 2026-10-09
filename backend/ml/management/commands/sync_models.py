from django.core.management.base import BaseCommand

from ml.services import sync_model_versions


class Command(BaseCommand):
    help = "Registra en la base de datos los modelos entrenados encontrados en ML_MODELS_DIR."

    def handle(self, *args, **options):
        versions = sync_model_versions()
        if not versions:
            self.stdout.write(self.style.WARNING("No se encontraron modelos. Ejecute: python ml/scripts/train.py"))
            return
        for version in versions:
            version.refresh_from_db()
            flag = " (ACTIVO)" if version.active else ""
            self.stdout.write(f"- {version.name} v{version.version} F1={version.metrics.get('f1')} "
                              f"ROC-AUC={version.metrics.get('roc_auc')}{flag}")
        self.stdout.write(self.style.SUCCESS(f"{len(versions)} versiones sincronizadas."))
