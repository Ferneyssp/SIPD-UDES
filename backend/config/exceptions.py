"""Manejador de errores de la API: siempre responde JSON con un 'detail' legible."""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict) and "detail" not in response.data:
            response.data = {"detail": "Los datos enviados no son válidos.", "errors": response.data}
        elif isinstance(response.data, list):
            response.data = {"detail": " ".join(str(item) for item in response.data)}
        return response

    if isinstance(exc, DjangoValidationError):
        return Response({"detail": "Los datos enviados no son válidos.", "errors": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, IntegrityError):
        logger.warning("Conflicto de integridad: %s", exc)
        return Response({"detail": "El registro entra en conflicto con información existente."}, status=status.HTTP_409_CONFLICT)

    logger.exception("Error no controlado en %s", context.get("view"))
    return Response({"detail": "Error interno del servidor. Intente nuevamente más tarde."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
