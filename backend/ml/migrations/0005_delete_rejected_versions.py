import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations


def delete_rejected_versions(apps, schema_editor):
    """Los modelos rechazados ya no se guardan: se eliminan sus registros y artefactos."""
    ModelVersion = apps.get_model("ml", "ModelVersion")
    ModelActivationLog = apps.get_model("ml", "ModelActivationLog")
    base = Path(settings.ML_MODELS_DIR).resolve()
    for version in ModelVersion.objects.filter(approval_status="RECHAZADO", active=False):
        if ModelActivationLog.objects.filter(new_version=version).exists():
            continue
        directory = (base / version.artifact_dir).resolve()
        if version.artifact_dir and not version.artifact_dir.startswith(".") and directory.parent == base:
            shutil.rmtree(directory, ignore_errors=True)
        version.delete()


class Migration(migrations.Migration):
    dependencies = [("ml", "0004_dataset_source_label")]

    operations = [migrations.RunPython(delete_rejected_versions, migrations.RunPython.noop)]
