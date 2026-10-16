"""
Punto de entrada de Django para Vercel (función Python serverless).

vercel.json reescribe /api/*, /admin/* y /static/* hacia esta función; el resto
de rutas lo sirve el build estático de React (frontend/dist).

En cada arranque en frío se preparan la base de datos y los modelos (equivalente
a backend/docker-entrypoint.sh): migraciones, registro de modelos ML y, si se
pide, datos SINTÉTICOS de demostración. Un candado de PostgreSQL evita que dos
instancias lo hagan a la vez.
"""
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402
from django.db import connection  # noqa: E402

logger = logging.getLogger("sipd.vercel")
BOOTSTRAP_LOCK_ID = 726_133_001


def _env_bool(name: str, default: bool) -> bool:
    return str(os.environ.get(name, str(default))).strip().lower() in {"1", "true", "yes", "si", "on"}


def _bootstrap() -> None:
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


if _env_bool("AUTO_MIGRATE", True):
    _bootstrap()

app = application = get_wsgi_application()
