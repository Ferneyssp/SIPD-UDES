"""Exportación de reportes a CSV y PDF (reportlab)."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Iterable

from django.conf import settings
from django.utils import timezone

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# Paleta de la interfaz (frontend/src/styles/global.css).
NAVY = "#1d3a5c"
BORDER = "#cfd7e0"
ALT_ROW = "#f7f9fb"
MUTED = "#6b7684"
LEVEL_COLORS = {"ALTO": "#d64545", "MEDIO": "#e89a2c", "BAJO": "#3f9d5a"}


# ---------------------------------------------------------------------------- CSV
def safe_cell(value):
    """Vacíos como celda vacía y texto que una hoja de cálculo interpretaría como fórmula, neutralizado."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def csv_rows(header: list[tuple[str, str]], rows: Iterable[dict]):
    """Genera el CSV por partes (UTF-8 con BOM para que Excel respete las tildes)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush():
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow([label for _, label in header])
    yield "﻿" + flush()
    for row in rows:
        writer.writerow([safe_cell(row.get(key)) for key, _ in header])
        yield flush()


# ---------------------------------------------------------------------------- PDF
def _fmt_date(value) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M") if timezone.is_aware(value) else value.strftime("%d/%m/%Y")
    return str(value)


def fmt_number(value, digits=3) -> str:
    if value is None:
        return "No calculado"
    if isinstance(value, float):
        return f"{value:.{digits}f}".replace(".", ",")
    return str(value)


class PdfReport:
    """Documento con encabezado institucional, tablas, gráficos de barras y numeración de páginas."""

    def __init__(self, title: str, subtitle: str = ""):
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

        self.colors = colors
        self.title, self.subtitle = title, subtitle
        base = getSampleStyleSheet()
        self.styles = {
            "title": ParagraphStyle("t", parent=base["Title"], fontSize=17, textColor=colors.HexColor(NAVY), alignment=0,
                                    spaceAfter=4),
            "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5, textColor=colors.HexColor(NAVY),
                                 spaceBefore=12, spaceAfter=6),
            "body": ParagraphStyle("b", parent=base["BodyText"], fontSize=9.5, leading=13),
            "muted": ParagraphStyle("m", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor(MUTED)),
            "cell": ParagraphStyle("c", parent=base["BodyText"], fontSize=8.5, leading=10.5),
        }
        self.story = []

    # --- bloques
    def heading(self, text):
        from reportlab.platypus import Paragraph

        self.story.append(Paragraph(text, self.styles["h2"]))

    def paragraph(self, text, style="body"):
        from reportlab.platypus import Paragraph
        from xml.sax.saxutils import escape

        self.story.append(Paragraph(escape(str(text)), self.styles[style]))

    def key_values(self, pairs: list[tuple[str, str]]):
        self.table(["Campo", "Valor"], [[k, v] for k, v in pairs], widths=[150, None], header=False)

    def table(self, headers: list[str], rows: list[list], widths=None, header=True):
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape

        if not rows:
            self.paragraph("Sin registros para los filtros seleccionados.", "muted")
            return
        colors = self.colors
        cell = self.styles["cell"]
        data = ([[Paragraph(f"<b>{escape(h)}</b>", cell) for h in headers]] if header else []) + [
            [Paragraph(escape("—" if v is None or v == "" else str(v)), cell) for v in row] for row in rows
        ]
        available = 515
        if widths:
            fixed = sum(w for w in widths if w)
            free = [w for w in widths if not w]
            widths = [w or (available - fixed) / len(free) for w in widths]
        table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        style = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(BORDER)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fa"))]
        for index in range(1 if header else 0, len(data)):
            if index % 2 == 0:
                style.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor(ALT_ROW)))
        table.setStyle(TableStyle(style))
        self.story += [table, Spacer(1, 6)]

    def bar_chart(self, categories: list[str], series: dict[str, list[float]], colors_by_series: dict[str, str],
                  caption: str, stacked: bool = True):
        """Barras horizontales (apiladas por nivel de riesgo). Los valores provienen de las mismas tablas del reporte."""
        from reportlab.graphics.charts.barcharts import HorizontalBarChart
        from reportlab.graphics.charts.legends import Legend
        from reportlab.graphics.shapes import Drawing, String

        if not categories or not any(any(v) for v in series.values()):
            return
        colors = self.colors
        height = max(90, 22 * len(categories) + 50)
        drawing = Drawing(515, height + 24)
        chart = HorizontalBarChart()
        chart.x, chart.y, chart.width, chart.height = 150, 30, 330, height - 20
        chart.data = [series[name] for name in series]
        chart.categoryAxis.categoryNames = [c[:32] for c in categories]
        chart.categoryAxis.labels.fontSize = 7.5
        chart.categoryAxis.labels.fontName = chart.valueAxis.labels.fontName = "Helvetica"
        chart.categoryAxis.reverseDirection = 1
        chart.valueAxis.valueMin = 0
        chart.valueAxis.labels.fontSize = 7.5
        chart.valueAxis.forceZero = 1
        if stacked:
            chart.categoryAxis.style = "stacked"
        for index, name in enumerate(series):
            chart.bars[index].fillColor = colors.HexColor(colors_by_series[name])
            chart.bars[index].strokeColor = colors.white
        legend = Legend()
        legend.x, legend.y = 150, 12
        legend.alignment = "right"
        legend.columnMaximum = 1
        legend.fontSize = 7.5
        legend.fontName = "Helvetica"
        legend.dx = legend.dy = 7
        legend.deltax = 70
        legend.colorNamePairs = [(colors.HexColor(colors_by_series[name]), name) for name in series]
        drawing.add(chart)
        drawing.add(legend)
        drawing.add(String(0, height + 12, caption, fontName="Helvetica", fontSize=8.5,
                            fillColor=colors.HexColor(MUTED)))
        self.story.append(drawing)

    # --- salida
    def render(self) -> bytes:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        title, subtitle, colors = self.title, self.subtitle, self.colors
        generated = timezone.localtime().strftime("%d/%m/%Y %H:%M")
        institution = settings.INSTITUTION_NAME

        class NumberedCanvas(canvas.Canvas):
            """Dibuja encabezado y pie con "Página X de Y" cuando ya se conoce el total de páginas."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._pages = []

            def showPage(self):
                self._pages.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total = len(self._pages)
                for state in self._pages:
                    self.__dict__.update(state)
                    self.setStrokeColor(colors.HexColor(NAVY))
                    self.setLineWidth(1.2)
                    self.line(2 * cm, A4[1] - 1.5 * cm, A4[0] - 2 * cm, A4[1] - 1.5 * cm)
                    self.setFont("Helvetica-Bold", 8.5)
                    self.setFillColor(colors.HexColor(NAVY))
                    self.drawString(2 * cm, A4[1] - 1.3 * cm, "SIPD · Sistema de Predicción y Seguimiento del Riesgo de Deserción")
                    self.setFont("Helvetica", 8)
                    self.setFillColor(colors.HexColor(MUTED))
                    self.drawRightString(A4[0] - 2 * cm, A4[1] - 1.3 * cm, institution[:70])
                    self.drawString(2 * cm, 1.2 * cm, f"Generado el {generated}")
                    self.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {self._pageNumber} de {total}")
                    super().showPage()
                super().save()

        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.2 * cm,
                                     bottomMargin=2 * cm, title=title, author="SIPD")
        head = [Paragraph(title, self.styles["title"])]
        if subtitle:
            from xml.sax.saxutils import escape

            head.append(Paragraph(escape(subtitle), self.styles["muted"]))
        head.append(Spacer(1, 6))
        document.build(head + self.story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()


def level_series(rows: list[dict]) -> dict[str, list[int]]:
    return {"Alto": [r["ALTO"] for r in rows], "Medio": [r["MEDIO"] for r in rows], "Bajo": [r["BAJO"] for r in rows]}


LEVEL_SERIES_COLORS = {"Alto": LEVEL_COLORS["ALTO"], "Medio": LEVEL_COLORS["MEDIO"], "Bajo": LEVEL_COLORS["BAJO"]}


def filters_text(filters: dict, labels: dict[str, str]) -> str:
    parts = [f"{labels.get(k, k)}: {v}" for k, v in filters.items() if v not in (None, "")]
    return " · ".join(parts) if parts else "Sin filtros"


def risk_pdf(report: dict) -> bytes:
    labels = {"period": "Periodo", "program": "Programa", "semester": "Semestre", "risk_level": "Nivel",
              "date_from": "Desde", "date_to": "Hasta"}
    pdf = PdfReport("Reporte de riesgo estudiantil", f"Filtros: {filters_text(report['filters'], labels)}")
    total = report["totals"]["students"]
    pdf.heading("Resumen ejecutivo")
    if not total:
        pdf.paragraph("No hay predicciones vigentes para los filtros seleccionados; el reporte no contiene datos.")
    else:
        levels = {item["code"]: item for item in report["totals"]["levels"]}
        pdf.paragraph(
            f"Se analizaron {total} estudiantes con predicción vigente. Riesgo estimado alto: {levels['ALTO']['count']} "
            f"({fmt_number(levels['ALTO']['pct'], 1)} %), medio: {levels['MEDIO']['count']} "
            f"({fmt_number(levels['MEDIO']['pct'], 1)} %), bajo: {levels['BAJO']['count']} "
            f"({fmt_number(levels['BAJO']['pct'], 1)} %)."
        )
        thresholds = report["thresholds"]
        pdf.paragraph(f"Umbrales vigentes: Bajo < {thresholds['low'] * 100:g} % · Medio < {thresholds['medium'] * 100:g} % "
                      f"· Alto ≥ {thresholds['medium'] * 100:g} %.", "muted")
        pdf.heading("Distribución por nivel de riesgo")
        pdf.table(["Nivel", "Estudiantes", "Porcentaje"],
                  [[i["label"], i["count"], f"{fmt_number(i['pct'], 1)} %"] for i in report["totals"]["levels"]],
                  widths=[200, None, None])
        pdf.heading("Distribución por programa académico")
        pdf.bar_chart([r["program"] for r in report["by_program"]], level_series(report["by_program"]),
                      LEVEL_SERIES_COLORS, "Estudiantes por nivel de riesgo estimado en cada programa")
        pdf.table(["Programa", "Total", "Alto", "Medio", "Bajo", "% Alto"],
                  [[r["program"], r["total"], r["ALTO"], r["MEDIO"], r["BAJO"], f"{fmt_number(r['ALTO_pct'], 1)} %"]
                   for r in report["by_program"]], widths=[190, None, None, None, None, None])
        pdf.heading("Distribución por semestre")
        pdf.table(["Semestre", "Total", "Alto", "Medio", "Bajo", "% Alto"],
                  [[r["semester"], r["total"], r["ALTO"], r["MEDIO"], r["BAJO"], f"{fmt_number(r['ALTO_pct'], 1)} %"]
                   for r in report["by_semester"]])
        pdf.heading("Versión del modelo utilizado")
        pdf.table(["Modelo", "Versión", "Predicciones"], [[m["model"], m["version"], m["predictions"]] for m in report["models"]])
    pdf.heading("Fuente de los datos y limitaciones")
    pdf.paragraph(report["source"])
    if report["scope_restricted"]:
        pdf.paragraph("El reporte se limita a los programas asignados al usuario que lo generó.")
    for notice in report["notices"]:
        pdf.paragraph(notice, "muted")
    return pdf.render()
