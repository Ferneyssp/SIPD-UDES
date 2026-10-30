import shutil

from django.core.management.base import BaseCommand

from ml.services import _models_dir, is_discarded_artifact


class Command(BaseCommand):
    help = ("Elimina de ML_MODELS_DIR los artefactos de versiones rechazadas o descartadas en la base de datos "
            "(sólo se conservan los modelos aprobados). Lo usa el flujo de GitHub Actions antes de publicar.")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Sólo lista lo que se eliminaría.")

    def handle(self, *args, **options):
        from sipd_ml.persistence import list_model_dirs, load_metadata

        models_dir = _models_dir()
        removed = 0
        for directory in list_model_dirs(models_dir) if models_dir.exists() else []:
            if not is_discarded_artifact(load_metadata(directory)):
                continue
            self.stdout.write(f"- {directory.name}")
            if not options["dry_run"]:
                shutil.rmtree(directory)
            removed += 1
        verb = "se eliminarían" if options["dry_run"] else "eliminadas"
        self.stdout.write(self.style.SUCCESS(f"{removed} carpetas de versiones descartadas {verb}."))
