from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from django.contrib.staticfiles import finders

from apps.solicitacoes.models import Solicitacao, AnexoOPO
from apps.solicitacoes.permissoes import pode_ver_mapa_eventos, escopo_unidades


def _tipo_opo_mapa(solicitacao):
    """Determina o tipo pela OPO mais recente: SIM = extraordinário; NÃO = ordinário."""
    anexo = (
        AnexoOPO.objects.filter(solicitacao=solicitacao)
        .exclude(arquivo="")
        .order_by("-criado_em")
        .first()
    )
    if not anexo:
        return "ORDINÁRIO"
    descricao = (anexo.descricao or "").upper()
    if "EVENTO EXTRA: SIM" in descricao:
        return "EXTRAORDINÁRIO"
    return "ORDINÁRIO"


@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    if not pode_ver_mapa_eventos(request.user):
        messages.error(request, "O mapa de eventos está disponível para gestores de CPR e Unidade.")
        return redirect("painel_gestao")

    eventos = (
        Solicitacao.objects
        .filter(unidade__in=escopo_unidades(request.user))
        .select_related("municipio", "bairro", "unidade")
        .order_by("data_evento", "hora_inicio")
    )

    data_inicio = (request.GET.get("data_inicio") or "").strip()
    data_fim = (request.GET.get("data_fim") or "").strip()

    if data_inicio:
        try:
            eventos = eventos.filter(data_evento__gte=datetime.strptime(data_inicio, "%Y-%m-%d").date())
        except ValueError:
            data_inicio = ""
    if data_fim:
        try:
            eventos = eventos.filter(data_evento__lte=datetime.strptime(data_fim, "%Y-%m-%d").date())
        except ValueError:
            data_fim = ""

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="mapa_eventos.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloMapa",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    subtitulo = ParagraphStyle(
        "SubtituloMapa",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    periodo = ParagraphStyle(
        "PeriodoMapa",
        parent=styles["Normal"],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#444444"),
        spaceAfter=8,
    )
    celula = ParagraphStyle("CelulaMapa", parent=styles["Normal"], fontSize=7, leading=8.2)
    cabecalho = ParagraphStyle(
        "CabecalhoMapa",
        parent=celula,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )

    story = []
    logo_path = finders.find("logos/logo_pmba.png")
    if logo_path:
        logo = Image(logo_path, width=18 * mm, height=18 * mm)
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 1.5 * mm))

    story.append(Paragraph("POLÍCIA MILITAR DA BAHIA", titulo))

    unidades_titulo = []
    for evento in eventos:
        if evento.unidade and evento.unidade.nome not in unidades_titulo:
            unidades_titulo.append(evento.unidade.nome)
    if len(unidades_titulo) == 1:
        unidade_titulo = unidades_titulo[0]
    elif unidades_titulo:
        unidade_titulo = " / ".join(unidades_titulo)
    else:
        unidade_titulo = "UNIDADE RESPONSÁVEL"

    story.append(Paragraph(f"MAPA DE EVENTO - {unidade_titulo}", subtitulo))

    if data_inicio and data_fim:
        periodo_texto = (
            f"Período: {datetime.strptime(data_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')} "
            f"a {datetime.strptime(data_fim, '%Y-%m-%d').strftime('%d/%m/%Y')}"
        )
    elif data_inicio:
        periodo_texto = f"A partir de {datetime.strptime(data_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')}"
    elif data_fim:
        periodo_texto = f"Até {datetime.strptime(data_fim, '%Y-%m-%d').strftime('%d/%m/%Y')}"
    else:
        periodo_texto = "Todos os eventos do âmbito institucional"
    story.append(Paragraph(periodo_texto, periodo))

    # Mantemos a coluna Hora e acrescentamos as colunas específicas de Início e Fim.
    # Hora continua representando a hora de referência do evento; Início e Fim
    # mostram explicitamente o intervalo operacional cadastrado na solicitação.
    rows = [[
        Paragraph("Data", cabecalho),
        Paragraph("Hora", cabecalho),
        Paragraph("Início", cabecalho),
        Paragraph("Fim", cabecalho),
        Paragraph("Evento", cabecalho),
        Paragraph("Município", cabecalho),
        Paragraph("Unidade que gerou", cabecalho),
        Paragraph("Tipo", cabecalho),
    ]]

    for evento in eventos:
        inicio = evento.hora_inicio.strftime("%H:%M") if evento.hora_inicio else "-"
        fim = evento.hora_fim.strftime("%H:%M") if evento.hora_fim else "-"
        hora_referencia = inicio
        rows.append([
            Paragraph(evento.data_evento.strftime("%d/%m/%Y"), celula),
            Paragraph(hora_referencia, celula),
            Paragraph(inicio, celula),
            Paragraph(fim, celula),
            Paragraph(str(evento.nome_evento or "-"), celula),
            Paragraph(str(evento.municipio.nome if evento.municipio else "-"), celula),
            Paragraph(str(evento.unidade.nome if evento.unidade else "-"), celula),
            Paragraph(_tipo_opo_mapa(evento), celula),
        ])

    tabela = Table(
        rows,
        repeatRows=1,
        colWidths=[22 * mm, 16 * mm, 18 * mm, 18 * mm, 55 * mm, 38 * mm, 70 * mm, 34 * mm],
        hAlign="CENTER",
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b5563")),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#9ca3af")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("POLÍCIA MILITAR DA BAHIA - Sistema Inteligente de Eventos", periodo))
    doc.build(story)
    return response
