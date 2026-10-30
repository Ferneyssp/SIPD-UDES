from django.db import migrations


def delete_rejected(apps, schema_editor):
    """Las cargas y los datasets de entrenamiento rechazados ya no se guardan: se eliminan los existentes."""
    DataUpload = apps.get_model("uploads", "DataUpload")
    for upload in DataUpload.objects.filter(status="RECHAZADO"):
        if upload.file:
            upload.file.delete(save=False)
        upload.delete()
    TrainingDataset = apps.get_model("ml", "TrainingDataset")
    TrainingDataset.objects.filter(status="RECHAZADO", runs__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("uploads", "0003_dataupload_content"), ("ml", "0005_delete_rejected_versions")]

    operations = [migrations.RunPython(delete_rejected, migrations.RunPython.noop)]
