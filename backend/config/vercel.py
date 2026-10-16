"""
Preparación del backend en Vercel (equivalente a backend/docker-entrypoint.sh).

Se ejecuta una vez por arranque en frío de la función: migraciones, registro de
modelos ML y, si se pide, datos SINTÉTICOS de demostración. Un candado de
PostgreSQL evita que dos instancias lo hagan a la vez.
"""
import logging
import os

from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)
BOOTSTRAP_LOCK_ID = 726_133_001


def _env_bool(name: str, default: bool) -> bool:
    return str(os.environ.get(name, str(default))).strip().lower() in {"1", "true", "yes", "si", "on"}


def bootstrap() -> None:
    if not _env_bool("AUTO_MIGRATE", True):
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [BOOTSTRAP_LOCK_ID])
    try:
        call_command("migrate", interactive=False, verbosity=0)
        call_command("sync_models", verbosity=0)
        if _env_bool("SEED_DEMO", False):
            from students.models import Student

            if not os.environ.get("DEMO_PASSWORD"):
                logger.warning("SEED_DEMO=true pero DEMO_PASSWORD no está definido: no se cargan datos demo.")
            elif not Student.objects.exists():
                call_command("seed_demo", students=int(os.environ.get("SEED_DEMO_STUDENTS", "120")))
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [BOOTSTRAP_LOCK_ID])
        connection.close()
