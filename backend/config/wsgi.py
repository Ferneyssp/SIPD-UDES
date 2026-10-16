import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()

if os.environ.get("VERCEL"):
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured

    from .vercel import bootstrap

    if settings.SECRET_KEY_MISSING and not settings.DEBUG:
        raise ImproperlyConfigured(
            "SECRET_KEY es obligatorio. Defínalo en Vercel: Settings > Environment Variables "
            "(Production y Preview) y vuelva a desplegar."
        )

    bootstrap()
