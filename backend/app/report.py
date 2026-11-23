"""Informe PDF de un análisis, pensado para el administrador de la tienda.

Contenido: resumen ejecutivo, acciones sugeridas por fila, detalle por fila, imagen anotada y
metodología con sus límites. Con la heurística (sin detector) el informe muestra solo la disponibilidad.
"""
import base64, io
from xml.sax.saxutils import escape
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#101827")
BLUE = colors.HexColor("#2563eb")
MUTED = colors.HexColor("#64748b")
LINE = colors.HexColor("#e2e8f0")
BG = colors.HexColor("#f4f6fa")
ESTADO_HEX = {"REPONER": "#dc2626", "REVISAR": "#ca8a04", "OK": "#16a34a"}
ESTADO_TEXT = {"REPONER": "Reponer", "REVISAR": "Revisar", "OK": "En orden"}
METODO = {"opencv-baseline": "Heurística OpenCV (sin entrenamiento)",
          "yolo-finetuned": "Detector YOLO entrenado (fine-tuning sobre Humans in the Loop)"}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=18,
                                textColor=NAVY, alignment=TA_LEFT, spaceAfter=2),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontName="Helvetica", fontSize=9, textColor=MUTED,
                              spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                             textColor=NAVY, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Helvetica", fontSize=9.5, leading=13,
                               textColor=NAVY),
        "small": ParagraphStyle("small", parent=base["Normal"], fontName="Helvetica", fontSize=8, leading=10.5,
                                textColor=MUTED),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=11,
                               textColor=NAVY),
        "cellb": ParagraphStyle("cellb", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11,
                                textColor=NAVY),
    }


def _kpi_table(items, st):
    cells = [[Paragraph(f'<font size=8 color="#64748b">{k}</font><br/><font size=15><b>{v}</b></font>', st["body"])
              for k, v in items]]
    t = Table(cells, colWidths=[(A4[0] - 4 * cm) / len(items)] * len(items))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _rows_table(filas, st):
    head = ["Fila", "Productos", "Frentes ocupados", "Libres", "Ocupación", "Estado", "Confianza"]
    data = [head]
    for f in filas:
        conf = "—" if f.get("confianza_media") is None else f"{f['confianza_media']:.0f}%"
        data.append([
            Paragraph(str(f["indice"]), st["cellb"]),
            Paragraph(str(f["productos"]), st["cell"]),
            Paragraph(f"{f['frentes_ocupados']} / {f['frentes_totales']}", st["cell"]),
            Paragraph(str(f["frentes_libres"]), st["cell"]),
            Paragraph(f"{f['ocupacion_pct']:.0f}%", st["cell"]),
            Paragraph(f'<font color="{ESTADO_HEX[f["estado"]]}"><b>{ESTADO_TEXT[f["estado"]]}</b></font>',
                      st["cell"]),
            Paragraph(conf, st["cell"]),
        ])
    widths = [1.3 * cm, 2.2 * cm, 3.2 * cm, 1.8 * cm, 2.2 * cm, 2.6 * cm, 2.2 * cm]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (4, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def _actions(filas, resumen):
    """Lista de acciones para el administrador, en orden de prioridad."""
    lines = []
    for f in filas:
        if f["estado"] == "REPONER":
            lines.append(f"<b>Fila {f['indice']}:</b> reponer aproximadamente <b>{f['frentes_libres']}</b> frente(s). "
                         f"Ocupación actual {f['ocupacion_pct']:.0f}% ({f['productos']} producto(s) detectados).")
    for f in filas:
        if f["estado"] == "REVISAR":
            lines.append(f"<b>Fila {f['indice']}:</b> revisar en tienda. Ocupación {f['ocupacion_pct']:.0f}%, "
                         f"{f['frentes_libres']} frente(s) libre(s) estimado(s).")
    if not lines:
        lines.append("Ninguna fila requiere reposición según la estimación actual.")
    return lines


def _report_story(analysis: dict):
    st = _styles()
    story = []
    fecha = analysis.get("created_at", "")[:19].replace("T", " ") or "—"
    conteo = analysis.get("conteo")
    metodo = METODO.get(analysis.get("method"), analysis.get("method", "—"))

    story.append(Paragraph("Informe de inventario de góndola", st["title"]))
    story.append(Paragraph(
        f"Análisis #{analysis.get('id')} · {fecha} · Archivo: {escape(analysis.get('filename', '—'))}<br/>"
        f"Método: {metodo}", st["sub"]))

    if analysis.get('pasillo'):
        story.append(Paragraph('Pasillo: '+escape(analysis['pasillo']),st['body']))
    if analysis.get('reference'):
        story.append(Paragraph('Referencia: '+escape(analysis['reference']),st['body']))
    if analysis.get('observations'):
        story.append(Paragraph('Observaciones: '+escape(analysis['observations']).replace('\n','<br/>'),st['body']))
    if analysis.get('low_threshold') is not None:
        story.append(Paragraph(f"Criterios guardados: crítico y alerta hasta {analysis['threshold']}% incluido; bajo por encima de ese valor y por debajo de {analysis['low_threshold']}%; suficiente desde {analysis['low_threshold']}%.",st['small']))
    story.append(Paragraph("Resumen", st["h2"]))
    if conteo:
        r = conteo["resumen"]
        ocup = "—" if r["ocupacion_pct"] is None else f"{r['ocupacion_pct']:.0f}%"
        story.append(_kpi_table([
            ("Productos detectados", r["productos"]),
            ("Filas", r["filas"]),
            ("Frentes ocupados", f"{r['frentes_ocupados']} / {r['frentes_totales']}"),
            ("Frentes a reponer", r["frentes_libres"]),
            ("Ocupación global", ocup),
        ], st))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"{'Ocupación útil estimada por frentes' if analysis.get('availability_basis') == 'useful_fronts' else 'Disponibilidad de superficie'}: <b>{analysis['availability_pct']}%</b>. "
            f"Umbral de alerta: {analysis['threshold']}%. "
            f"Filas a reponer: <b>{r['filas_reponer']}</b>; filas a revisar: <b>{r['filas_revisar']}</b>.",
            st["body"]))

        if analysis.get('availability_basis') == 'useful_fronts':
            story.append(Paragraph(
                f"Espacios útiles para reponer: {analysis.get('useful_free_fronts', 0)}. "
                f"Superficie ocupada: {analysis.get('surface_availability_pct')}%. "
                f"Superficie vacía: {analysis.get('surface_empty_pct')}%. "
                "La ocupación útil usa frentes ocupados / (ocupados + libres útiles). "
                "Las marcas rojas indican posiciones estimadas donde cabe una caja de referencia; "
                "no garantizan capacidad física en profundidad.", st['body']))
        story.append(Paragraph("Acciones sugeridas", st["h2"]))
        for line in _actions(conteo["filas"], r):
            story.append(Paragraph("• " + line, st["body"]))
            story.append(Spacer(1, 3))
        story.append(Spacer(1, 2))
        story.append(Paragraph(
            "Los frentes a reponer son una estimación a partir del ancho de frente medido. El pedido final debe "
            "validarse con el conteo físico y con el inventario del sistema.", st["small"]))

        story.append(Paragraph("Detalle por fila", st["h2"]))
        if conteo["filas"]:
            story.append(_rows_table(conteo["filas"], st))
        else:
            story.append(Paragraph("No se detectaron productos dentro de la región analizada.", st["body"]))
    else:
        story.append(_kpi_table([
            ("Disponibilidad", ("Sin evaluar" if analysis["availability_pct"] is None else f"{analysis['availability_pct']}%")),
            ("Espacio vacío", ("Sin evaluar" if analysis["empty_pct"] is None else f"{analysis['empty_pct']}%")),
            ("Umbral de alerta", f"{analysis['threshold']}%"),
        ], st))
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Este resultado no contiene un detalle de detecciones por estante. Consulta el método y las advertencias guardadas en el análisis.", st["body"]))

    if analysis.get("warnings"):
        story.append(Paragraph("Advertencias de calidad", st["h2"]))
        for w in analysis["warnings"]:
            story.append(Paragraph("• " + w, st["body"]))

    story.append(PageBreak())
    story.append(Paragraph("Imagen analizada", st["h2"]))
    img = ImageReader(io.BytesIO(base64.b64decode(analysis["overlay_jpg_b64"])))
    iw, ih = img.getSize()
    max_w = A4[0] - 4 * cm
    max_h = A4[1] - 9 * cm
    scale = min(max_w / iw, max_h / ih)
    story.append(Image(io.BytesIO(base64.b64decode(analysis["overlay_jpg_b64"])), width=iw * scale, height=ih * scale))
    story.append(Paragraph(
        "Leyenda: verde = producto detectado · rojo = espacio vacío dentro de la región · gris = excluido. "
        "Las etiquetas N y F identifican nivel y frente.", st["small"]))

    story.append(Paragraph("Metodología y límites", st["h2"]))
    det_line = "Las métricas de evaluación y el origen de los datos del detector se documentan por separado. La confianza de una detección no equivale a la exactitud del porcentaje de disponibilidad."
    items = [
        "El detector distingue producto de no producto. No identifica marcas ni SKU, por lo que el pedido se expresa "
        "en frentes; el administrador lo traduce a productos concretos.",
        "Un frente es una columna de producto dentro de una fila. Productos apilados cuentan como un solo frente.",
        "Las filas se forman agrupando productos por altura, salvo que se indique el número de estantes. "
        "Un estante vacío sin número de filas indicado no aparece en el conteo.",
        "El espacio vacío se mide como superficie dentro de la región y fuera de productos. Incluye fondo visible "
        "entre productos, por lo que no equivale a frentes libres exactos.",
        "No se mide la precisión del espacio vacío: no existe una referencia etiquetada para esa categoría.",
        det_line,
    ]
    for it in items:
        story.append(Paragraph("• " + it, st["body"]))
        story.append(Spacer(1, 3))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Proyecto académico Capstone. No es un producto oficial de Walmart.", st["small"]))

    return story


def _document(story, title, subtitle):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=1.8*cm, bottomMargin=1.8*cm, title=title, author="REGOVA")
    def footer(canv, document):
        canv.saveState()
        canv.setStrokeColor(LINE)
        canv.line(2*cm,1.3*cm,A4[0]-2*cm,1.3*cm)
        canv.setFont("Helvetica",7.5)
        canv.setFillColor(MUTED)
        canv.drawString(2*cm,0.9*cm,subtitle)
        canv.drawRightString(A4[0]-2*cm,0.9*cm,f"Página {document.page}")
        canv.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return buf.getvalue()


def build_pdf(analysis: dict) -> bytes:
    return _document(_report_story(analysis), "REGOVA - Reporte de análisis",
                     f"REGOVA - Análisis #{analysis.get('id')} - Proyecto académico")


def build_grouped_pdf(analyses: list[dict]) -> bytes:
    if not analyses:
        raise ValueError("Selecciona al menos un reporte")
    st = _styles()
    dates = sorted(a.get('created_at','') for a in analyses if a.get('created_at'))
    fmt = lambda date: date[:19].replace('T',' ') + ' UTC'
    story = [Spacer(1,1*cm),Paragraph("REGOVA",st['title']),
             Paragraph("Reportes agrupados",st['title']),
             Paragraph(f"Generado: {datetime.now(timezone.utc).strftime('%d-%m-%Y %H:%M')} UTC",st['sub']),
             Paragraph(f"{len(analyses)} reportes seleccionados",st['h2'])]
    if dates:
        story.append(Paragraph(f"Período de análisis: {fmt(dates[0])} a {fmt(dates[-1])}",st['body']))
    counts = {key: sum(a.get('criticality')==key for a in analyses) for key in ['aceptable','baja','critica','no_evaluable']}
    story += [Spacer(1,14),_kpi_table([('Aceptables',counts['aceptable']),('Bajos',counts['baja']),
               ('Críticos',counts['critica']),('Sin evaluar',counts['no_evaluable'])],st),Spacer(1,14),
               Paragraph('Este documento reúne reportes existentes. Cada resultado conserva los criterios y valores utilizados al analizar la fotografía; no se recalculan ni se mezclan sus porcentajes.',st['body']),
               Paragraph('Las fechas del PDF se muestran en UTC. El orden corresponde a la selección enviada desde la tabla.',st['small']),
               Paragraph('Reportes incluidos',st['h2'])]
    data=[['Análisis','Archivo','Fecha de análisis (UTC)','Estado']]
    labels={'aceptable':'Aceptable','baja':'Bajo','critica':'Crítico','no_evaluable':'Sin evaluar'}
    for analysis in analyses:
        data.append([Paragraph(f"#{analysis['id']}",st['cellb']),
                     Paragraph(escape(analysis.get('filename','Sin nombre')),st['cell']),
                     Paragraph(escape(analysis.get('created_at','')[:19].replace('T',' ')),st['cell']),
                     Paragraph(labels.get(analysis.get('criticality'),'Sin evaluar'),st['cell'])])
    table=Table(data,colWidths=[2*cm,6.2*cm,5.5*cm,3.3*cm],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),
                  ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,BG]),('VALIGN',(0,0),(-1,-1),'TOP'),
                  ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),0.3,LINE)]))
    story.append(table)
    for analysis in analyses:
        story.append(PageBreak())
        story.extend(_report_story(analysis))
    return _document(story,'REGOVA - Reportes agrupados','REGOVA - Reportes agrupados - Proyecto académico')
