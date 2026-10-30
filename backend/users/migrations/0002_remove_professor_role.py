from django.db import migrations, models


def professors_to_coordinators(apps, schema_editor):
    """El rol Profesor se elimina: sus usuarios pasan a Coordinador con los mismos programas
    (conservan seguimientos y auditoría)."""
    User = apps.get_model("users", "User")
    User.objects.filter(role="PROFESSOR").update(role="COORDINATOR")


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]

    operations = [
        migrations.RunPython(professors_to_coordinators, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(choices=[("ADMIN", "Administrador"), ("COORDINATOR", "Coordinador académico")],
                                   default="COORDINATOR", max_length=20, verbose_name="rol"),
        ),
        migrations.AlterField(
            model_name="user",
            name="programs",
            field=models.ManyToManyField(blank=True, help_text="Programas académicos que el coordinador puede consultar. Sin programas asignados no ve estudiantes (el acceso se deniega por defecto).", related_name="users", to="academic.program"),
        ),
    ]
