import os
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import escopo_unidades


def _tipo_evento_por_opo(solicitacao):
    """Obtém o tipo a partir da última OPO gerada para a solicitação.

    A escolha SIM/NÃO do evento extra é registrada na descrição do AnexoOPO.
    Se houver mais de uma OPO, a última gerada é a referência vigente.
    """
    opos = list(solicitacao.opos.all().order_by("-criado_em", "-id"))
    if not opos:
        return "ORDINÁRIO"

    descricao = (opos[0].descricao or "").upper()
    if "EVENTO EXTRA: SIM" in descricao:
        return "EXTRAORDINÁRIO"
    return "ORDINÁRIO"


@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    inicio_raw = (request.GET.get("data_inicio") or "").strip()
    fim_raw = (request.GET.get("data_fim") or "").strip()
    hoje = timezone.localdate()

    try:
        inicio = timezone.datetime.strptime(inicio_raw, "%Y-%m-%d").date() if inicio_raw else hoje
    except ValueError:
        inicio = hoje

    try:
        fim = timezone.datetime.strptime(fim_raw, "%Y-%m-%d").date() if fim_raw else inicio
    except ValueError:
        fim = inicio

    if fim < inicio:
        inicio, fim = fim, inicio

    eventos = (
        Solicitacao.objects.filter(
            unidade__in=escopo_unidades(request.user),
            data_evento__range=(inicio, fim),
        )
        .select_related("municipio", "unidade")
        .prefetch_related("opos")
        .order_by("data_evento", "hora_inicio")
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="mapa_eventos.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Mapa de Eventos - SiEv",
        author="Sistema Inteligente de Eventos - SiEv",
    )

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "MapaTitulo",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    subtitulo = ParagraphStyle(
        "MapaSubtitulo",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    periodo = ParagraphStyle(
        "MapaPeriodo",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#444444"),
        spaceAfter=10,
    )
    celula = ParagraphStyle(
        "CelulaMapa",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
    )
    celula_cab = ParagraphStyle(
        "CabMapa",
        parent=celula,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    elementos = []

    logo_path = finders.find("logos/logo_pmba.png")
    if logo_path and os.path.exists(logo_path):
        logo = Image(logo_path, width=22 * mm, height=22 * mm, kind="proportional")
        logo.hAlign = "CENTER"
        elementos.append(logo)
        elementos.append(Spacer(1, 2 * mm))

    elementos.append(Paragraph("POLÍCIA MILITAR DA BAHIA", titulo))
    elementos.append(Paragraph("MAPA DE EVENTO - UNIDADE QUE GEROU", subtitulo))
    elementos.append(Paragraph(
        f"Período: {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}",
        periodo,
    ))

    cabecalho = [
        Paragraph("DATA", celula_cab),
        Paragraph("HORA", celula_cab),
        Paragraph("EVENTO", celula_cab),
        Paragraph("MUNICÍPIO", celula_cab),
        Paragraph("UNIDADE QUE GEROU", celula_cab),
        Paragraph("TIPO", celula_cab),
    ]
    rows = [cabecalho]

    for evento in eventos:
        unidade = evento.unidade.sigla if evento.unidade else "-"
        municipio = evento.municipio.nome if evento.municipio else "-"
        tipo = _tipo_evento_por_opo(evento)
        rows.append([
            Paragraph(evento.data_evento.strftime("%d/%m/%Y"), celula),
            Paragraph(evento.hora_inicio.strftime("%H:%M"), celula),
            Paragraph(evento.nome_evento or "-", celula),
            Paragraph(municipio, celula),
            Paragraph(unidade, celula),
            Paragraph(tipo, celula),
        ])

    if len(rows) == 1:
        rows.append([Paragraph("Nenhum evento encontrado no período informado.", celula), "", "", "", "", ""])

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[24 * mm, 20 * mm, 70 * mm, 48 * mm, 65 * mm, 35 * mm],
        hAlign="CENTER",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5A463D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#777777")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("ALIGN", (5, 1), (5, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    elementos.append(table)
    elementos.append(Spacer(1, 8 * mm))
    elementos.append(Paragraph(
        "Sistema Inteligente de Eventos - SiEv | Polícia Militar da Bahia",
        ParagraphStyle("Rodape", parent=styles["Normal"], fontSize=7, alignment=TA_CENTER, textColor=colors.grey),
    ))

    doc.build(elementos)
    return response
