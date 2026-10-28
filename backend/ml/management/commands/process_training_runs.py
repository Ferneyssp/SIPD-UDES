import time

from django.core.management.base import BaseCommand

from ml.models import RunStatus, TrainingRun
from ml.training_service import execute_run, fail_stale_runs


class Command(BaseCommand):
    help = ("Ejecuta los reentrenamientos pendientes solicitados desde la web (ML_TRAINING_EXECUTOR=worker). "
            "Debe usar el mismo ML_MODELS_DIR y la misma base de datos que el backend.")

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Procesa lo pendiente y termina.")
        parser.add_argument("--interval", type=int, default=10, help="Segundos entre revisiones (modo continuo).")

    def handle(self, *args, **options):
        while True:
            fail_stale_runs()
            pending = TrainingRun.objects.filter(status=RunStatus.PENDING).order_by("created_at").values_list("pk", flat=True)
            for run_id in list(pending):
                self.stdout.write(f"Ejecutando entrenamiento #{run_id}...")
                execute_run(run_id)
                run = TrainingRun.objects.get(pk=run_id)
                self.stdout.write(f"  -> {run.get_status_display()}: {run.stage_message}")
            if options["once"]:
                return
            time.sleep(options["interval"])
