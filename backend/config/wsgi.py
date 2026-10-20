import json
import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _unavailable(message: str):
    """App WSGI mínima: responde 503 con un mensaje claro en lugar de tumbar la función."""
    body = json.dumps({"detail": message}, ensure_ascii=False).encode("utf-8")

    def app(environ, start_response):
        start_response("503 Service Unavailable", [("Content-Type", "application/json; charset=utf-8"),
                                                   ("Content-Length", str(len(body)))])
        return [body]

    return app


if os.environ.get("VERCEL"):
    try:
        application = get_wsgi_application()
        from django.conf import settings

        from .vercel import bootstrap

        if settings.SECRET_KEY_MISSING and not settings.DEBUG:
            # Nunca se atiende la aplicación con la clave provisional del build.
            application = _unavailable(
                "Falta la variable SECRET_KEY. Defínala en Vercel (Settings > Environment Variables, "
                "Production y Preview) y vuelva a desplegar."
            )
        else:
            bootstrap()
    except Exception:
        logging.getLogger(__name__).exception("El backend no pudo iniciar en Vercel.")
        application = _unavailable("El backend no pudo iniciar. Revise los logs de la función en Vercel.")
else:
    application = get_wsgi_application()
