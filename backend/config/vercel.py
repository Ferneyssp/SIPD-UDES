"""
Preparación del backend en Vercel (equivalente a backend/docker-entrypoint.sh).

Se ejecuta una vez por arranque en frío de la función: migraciones, registro de
modelos ML y, si se pide, datos SINTÉTICOS de demostración. Un candado de
PostgreSQL evita que dos instancias lo hagan a la vez. Si algo falla, el error
queda en los logs y la API sigue arrancando, de modo que /api/health/ puede
informar el estado de la base de datos.
"""
import logging
import os
import time

from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)
BOOTSTRAP_LOCK_ID = 726_133_001
LOCK_WAIT_SECONDS = 20


def _env_bool(name: str, default: bool) -> bool:
    return str(os.environ.get(name, str(default))).strip().lower() in {"1", "true", "yes", "si", "on"}


def _try_lock() -> bool:
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [BOOTSTRAP_LOCK_ID])
            if cursor.fetchone()[0]:
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(1)


def _prepare() -> None:
    call_command("migrate", interactive=False, verbosity=0)
    call_command("sync_models", verbosity=0)
    if _env_bool("SEED_DEMO", False):
        from students.models import Student

        if not os.environ.get("DEMO_PASSWORD"):
            logger.warning("SEED_DEMO=true pero DEMO_PASSWORD no está definido: no se cargan datos demo.")
        elif not Student.objects.exists():
            call_command("seed_demo", students=int(os.environ.get("SEED_DEMO_STUDENTS", "120")))


def bootstrap() -> None:
    if not _env_bool("AUTO_MIGRATE", True):
        return
    try:
        if not _try_lock():
            logger.warning("Otra instancia está preparando la base de datos; se omite el arranque en esta.")
            return
        try:
            _prepare()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [BOOTSTRAP_LOCK_ID])
    except Exception:
        logger.exception("Falló la preparación de la base de datos en Vercel (migraciones, modelos o datos demo).")
    finally:
        connection.close()
