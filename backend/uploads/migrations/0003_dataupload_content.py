from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("uploads", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataupload",
            name="content",
            field=models.BinaryField(blank=True, editable=False, null=True),
        ),
    ]
