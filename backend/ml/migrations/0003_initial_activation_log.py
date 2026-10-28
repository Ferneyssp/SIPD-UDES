from django.db import migrations


def record_current_active(apps, schema_editor):
    """Deja constancia de la versión que ya estaba activa antes del módulo de reentrenamiento,
    para que pueda recuperarse más adelante."""
    ModelVersion = apps.get_model("ml", "ModelVersion")
    ModelActivationLog = apps.get_model("ml", "ModelActivationLog")
    active = ModelVersion.objects.filter(active=True).first()
    if active and not ModelActivationLog.objects.exists():
        ModelActivationLog.objects.create(action="INICIAL", new_version=active, new_label=f"{active.name} v{active.version}")


class Migration(migrations.Migration):
    dependencies = [("ml", "0002_training_and_versioning")]

    operations = [migrations.RunPython(record_current_active, migrations.RunPython.noop)]
