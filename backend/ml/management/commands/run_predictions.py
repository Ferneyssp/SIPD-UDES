from django.core.management.base import BaseCommand, CommandError

from academic.models import AcademicPeriod
from ml.services import ModelNotAvailableError
from predictions.services import predict_period


class Command(BaseCommand):
    help = "Genera predicciones (nuevos registros históricos) para un periodo académico."

    def add_arguments(self, parser):
        parser.add_argument("--period", help="Código del periodo (por defecto el actual)")

    def handle(self, *args, **options):
        period = AcademicPeriod.objects.filter(code=options["period"]).first() if options["period"] else AcademicPeriod.get_current()
        if period is None:
            raise CommandError("No existe el periodo indicado.")
        try:
            total = predict_period(period)
        except ModelNotAvailableError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"{total} predicciones generadas para {period.code}."))
