"""
Carga datos de DEMOSTRACIÓN 100% SINTÉTICOS.

    python manage.py seed_demo                 # 240 estudiantes ficticios
    python manage.py seed_demo --students 400 --reset

No usa información personal real. Los estudiantes se identifican con
códigos E001, E002, ... y los usuarios son cuentas de prueba.
"""
import os
import random
from datetime import date, datetime, time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from academic.models import AcademicPeriod, AcademicRecord, Program
from followups.models import FollowUp, FollowUpStatus, InterventionType
from ml.services import ModelNotAvailableError, sync_model_versions
from predictions.models import Prediction, PredictionStatus
from predictions.services import predict_period
from students.models import Student
from users.models import Role, User

PROGRAMS = [
    ("SIS", "Ingeniería de Sistemas"),
    ("SOF", "Ingeniería de Software"),
    ("CIV", "Ingeniería Civil"),
    ("IND", "Ingeniería Industrial"),
    ("ELE", "Ingeniería Electrónica"),
]
PERIODS = [
    ("2025-1", date(2025, 2, 3), date(2025, 6, 13)),
    ("2025-2", date(2025, 8, 4), date(2025, 12, 5)),
    ("2026-1", date(2026, 2, 2), date(2026, 6, 12)),
    ("2026-2", date(2026, 8, 3), date(2026, 12, 4)),
]
DEMO_USERS = [
    # username, email, nombre, apellido, rol, programas
    ("admin", "admin@sipd.demo", "Administrador", "Demo", Role.ADMIN, []),
    ("coordinador", "coordinador@sipd.demo", "Coordinación", "Académica", Role.COORDINATOR, []),
    ("profesor", "profesor@sipd.demo", "Docente", "Sistemas", Role.PROFESSOR, ["SIS", "SOF"]),
    ("profesor2", "profesor2@sipd.demo", "Docente", "Civil", Role.PROFESSOR, ["CIV", "IND"]),
]
OBSERVATIONS = [
    "Se programó plan de estudio con tutor asignado para reforzar asignaturas básicas.",
    "No se logró contacto telefónico; se enviará correo institucional.",
    "Remitido a bienestar universitario para orientación psicopedagógica.",
    "Reunión con acudiente para informar la situación académica del periodo.",
    "Se orientó sobre convocatoria de apoyo económico institucional.",
    "Ajuste de carga académica acordado con la coordinación del programa.",
]


class Command(BaseCommand):
    help = "Crea datos de demostración sintéticos (programas, periodos, usuarios, estudiantes, predicciones)."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=240)
        parser.add_argument("--reset", action="store_true", help="Elimina estudiantes, predicciones y seguimientos previos")
        parser.add_argument("--seed", type=int, default=2026)

    def handle(self, *args, **options):
        from sipd_ml.synthetic import simulate_student_trajectories

        password = os.environ.get("DEMO_PASSWORD") or "SipdDemo2026*"
        random.seed(options["seed"])

        with transaction.atomic():
            if options["reset"]:
                FollowUp.objects.all().delete()
                Prediction.objects.all().delete()
                AcademicRecord.objects.all().delete()
                Student.objects.all().delete()
            programs = {code: Program.objects.update_or_create(code=code, defaults={"name": name})[0] for code, name in PROGRAMS}
            periods = {}
            for code, start, end in PERIODS:
                periods[code], _ = AcademicPeriod.objects.update_or_create(
                    code=code, defaults={"start_date": start, "end_date": end, "is_current": code == PERIODS[-1][0]}
                )
            AcademicPeriod.objects.filter(code=PERIODS[-1][0]).update(is_current=True)
            users = {}
            for username, email, first, last, role, program_codes in DEMO_USERS:
                user, created = User.objects.get_or_create(
                    username=username, defaults={"email": email, "first_name": first, "last_name": last, "role": role}
                )
                if created:
                    user.set_password(password)
                    user.is_staff = role == Role.ADMIN
                    user.is_superuser = role == Role.ADMIN
                    user.save()
                user.programs.set([programs[c] for c in program_codes])
                users[username] = user

            rows = simulate_student_trajectories(options["students"], [p[0] for p in PERIODS], seed=options["seed"])
            last_row = {}
            for row in rows:
                last_row[row["student_code"]] = row
            students = {}
            for code, row in last_row.items():
                students[code], _ = Student.objects.update_or_create(
                    anonymous_code=code,
                    defaults={"program": programs[row["program_code"]], "semester": row["semester"],
                              "academic_status": row["academic_status"], "current_period": periods[row["academic_period"]],
                              "is_active": row["academic_status"] != "Retirado"},
                )
            for row in rows:
                AcademicRecord.objects.update_or_create(
                    student=students[row["student_code"]], academic_period=periods[row["academic_period"]],
                    defaults={k: row[k] for k in (
                        "semester", "academic_status", "gpa", "credits_enrolled", "credits_approved", "credits_failed",
                        "failed_subjects", "attendance_percentage", "course_repetitions", "works_while_studying",
                        "socioeconomic_stratum", "financial_difficulty", "motivation_level")},
                )
        self.stdout.write(f"Estudiantes sintéticos: {len(students)} | registros académicos: {len(rows)}")

        sync_model_versions()
        try:
            for code, _, end in PERIODS:
                total = predict_period(periods[code])
                # Sólo para la demo: fecha de predicción al cierre del periodo (o hoy si es el actual)
                moment = timezone.make_aware(datetime.combine(min(end, date.today()), time(9, 0)))
                Prediction.objects.filter(academic_period=periods[code]).update(prediction_date=moment)
                self.stdout.write(f"  Predicciones {code}: {total}")
        except ModelNotAvailableError as exc:
            self.stdout.write(self.style.WARNING(f"Sin predicciones: {exc}"))

        self._create_followups(users, periods[PERIODS[-1][0]])
        call_command("check")
        self.stdout.write(self.style.SUCCESS("\nDatos de demostración creados (SINTÉTICOS)."))
        self.stdout.write("Usuarios de prueba (contraseña definida en DEMO_PASSWORD o valor por defecto de desarrollo):")
        for username, *_rest in DEMO_USERS:
            self.stdout.write(f"  - {username}")

    def _create_followups(self, users, period):
        if FollowUp.objects.exists():
            return
        responsibles = [users["coordinador"], users["profesor"], users["profesor2"]]
        high_risk = (
            Prediction.objects.filter(academic_period=period, status=PredictionStatus.CURRENT, risk_level="ALTO")
            .select_related("student").order_by("-probability")[:45]
        )
        statuses = list(FollowUpStatus.values)
        types = list(InterventionType.values)[:-1]
        for index, prediction in enumerate(high_risk):
            if index % 3 == 2:
                continue  # algunos estudiantes quedan sin seguimiento
            responsible = responsibles[index % len(responsibles)]
            FollowUp.objects.create(
                student=prediction.student, user=responsible, created_by=responsible, academic_period=period,
                intervention_type=types[index % len(types)], status=statuses[index % len(statuses)],
                observation=OBSERVATIONS[index % len(OBSERVATIONS)],
                follow_up_date=min(date.today(), period.end_date) if period.end_date else date.today(),
            )
