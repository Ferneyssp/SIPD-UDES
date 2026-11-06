"""
Reporte automático por correo a los coordinadores después de ejecutar la predicción de un periodo.

Cada coordinador activo con correo y programas incluidos en la ejecución recibe el reporte de riesgo de SUS
programas (mismo cálculo y mismo PDF que el módulo Reportes, con su alcance). Un correo que falla no
afecta la predicción: el error queda en el registro del servidor.
"""
from __future__ import annotations

import logging
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from reports.exporters import risk_pdf
from reports.services import risk_report
from users.models import Role, User
from users.password_reset import email_configured

logger = logging.getLogger(__name__)


def report_recipients(program_ids=None) -> list[User]:
    """Coordinadores activos con correo cuyo ámbito incluye alguno de los programas procesados."""
    recipients = []
    users = User.objects.filter(is_active=True, role=Role.COORDINATOR).exclude(email="").prefetch_related("programs")
    for user in users:
        scope = {program.pk for program in user.programs.all()}
        if scope and (program_ids is None or scope & set(program_ids)):
            recipients.append(user)
    return recipients


def _message(user: User, period_code: str, report: dict, connection) -> EmailMultiAlternatives:
    total = report["totals"]["students"]
    levels = {item["code"]: item for item in report["totals"]["levels"]}
    programs = ", ".join(row["program"] for row in report["by_program"]) or "sus programas"
    link = f"{settings.FRONTEND_URL.rstrip('/')}/reportes?period={period_code}"
    name = user.get_full_name() or user.username
    summary = [(levels[code]["label"], levels[code]["count"], levels[code]["pct"]) for code in ("ALTO", "MEDIO", "BAJO")]
    subject = f"SADE · Reporte de riesgo {period_code}"
    text = (
        f"Hola {name}:\n\n"
        f"Se ejecutó la predicción del periodo {period_code}. Resumen de {programs}:\n"
        f"- Estudiantes con predicción vigente: {total}\n"
        + "".join(f"- Riesgo {label.lower()}: {count} ({pct} %)\n" for label, count, pct in summary)
        + f"\nEl reporte completo va adjunto en PDF y puede consultarlo en {link}\n\n"
        "El nivel de riesgo es una estimación para apoyar el acompañamiento académico, no una certeza.\n\n"
        f"SADE · {settings.INSTITUTION_NAME}"
    )
    rows = "".join(
        f'<tr><td style="padding:6px 12px;border-bottom:1px solid #e3e8ef">Riesgo {escape(label.lower())}</td>'
        f'<td style="padding:6px 12px;border-bottom:1px solid #e3e8ef;text-align:right"><strong>{count}</strong> ({pct} %)</td></tr>'
        for label, count, pct in summary
    )
    html = f"""<div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#1f2a37">
  <img src="{escape(settings.FRONTEND_URL.rstrip('/'))}/escudo-udes.png" alt="Universidad de Santander" width="64" height="64">
  <h2 style="color:#1d3a5c">Reporte de riesgo · {escape(period_code)}</h2>
  <p>Hola {escape(name)}:</p>
  <p>Se ejecutó la predicción del periodo <strong>{escape(period_code)}</strong>. Resumen de {escape(programs)}:</p>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:6px 12px;border-bottom:1px solid #e3e8ef">Estudiantes con predicción vigente</td>
    <td style="padding:6px 12px;border-bottom:1px solid #e3e8ef;text-align:right"><strong>{total}</strong></td></tr>
    {rows}
  </table>
  <p>El reporte completo va adjunto en PDF.</p>
  <p><a href="{escape(link)}" style="background:#1d3a5c;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none">Ver en SADE</a></p>
  <p style="font-size:12px;color:#6b7684">El nivel de riesgo es una estimación para apoyar el acompañamiento académico, no una certeza.<br>
  SADE · {escape(settings.INSTITUTION_NAME)}</p>
</div>"""
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email], connection=connection)
    message.attach_alternative(html, "text/html")
    message.attach(f"sade_reporte_riesgo_{period_code}.pdf", risk_pdf(report), "application/pdf")
    return message


def send_program_reports(period_code: str, program_ids=None, program_code: str | None = None) -> dict:
    """Envía el reporte a cada coordinador. Devuelve cuántos correos se enviaron y cuántos fallaron."""
    recipients = report_recipients(program_ids)
    result = {"sent": 0, "failed": 0}
    if not recipients:
        return result
    if not email_configured():
        logger.error("Correo no configurado en Vercel: no se enviaron los reportes de %s a %s coordinadores.",
                     period_code, len(recipients))
        result["failed"] = len(recipients)
        return result
    params = {"period": period_code, **({"program": program_code} if program_code else {})}
    connection = get_connection()
    try:
        for user in recipients:
            try:
                _message(user, period_code, risk_report(user, params), connection).send()
                result["sent"] += 1
            except Exception:  # noqa: BLE001 - un correo fallido no detiene los demás ni la predicción
                logger.exception("No se pudo enviar el reporte de %s al usuario %s", period_code, user.pk)
                result["failed"] += 1
    finally:
        connection.close()
    return result
