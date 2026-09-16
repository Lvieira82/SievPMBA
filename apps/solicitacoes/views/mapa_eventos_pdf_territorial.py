from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.staticfiles import finders

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import pode_ver_mapa_eventos, escopo_unidades
from .mapa_eventos_pdf import gerar_mapa_eventos_pdf_seguro as _gerar_mapa_eventos_pdf_original
from .mapa_eventos_pdf import _tipo_opo_mapa, _unidade_titulo


def _eventos_mapa_territorial_pdf(request):
    """Aplica ao PDF o mesmo escopo territorial da visão CPR do mapa.

    Para CPR, o território é definido pelo município do evento. Portanto,
    qualquer OPO/evento localizado em município pertencente ao CPR aparece,
    independentemente da unidade que gerou a OPO.

    Para Unidade, permanece o escopo restrito à própria unidade.
    """
    acesso = getattr(request.user, "acesso_institucional", None)
    base = Solicitacao.objects.select_related(
        "municipio", "municipio__unidade_responsavel", "municipio__unidade_responsavel__cpr", "bairro", "unidade"
    ).order_by("data_evento", "hora_inicio")

    if acesso and acesso.perfil == "CPR" and acesso.cpr_id:
        return base.filter(municipio__unidade_responsavel__cpr_id=acesso.cpr_id)

    return base.filter(unidade__in=escopo_unidades(request.user))


@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    # Os relatórios de cumprimento continuam exatamente na view original.
    if request.GET.get("relatorio") == "cumprimentos":
        return _gerar_mapa_eventos_pdf_original(request)

    if not pode_ver_mapa_eventos(request.user):
        messages.error(request, "O mapa de eventos está disponível para gestores de CPR e Unidade.")
        return redirect("painel_gestao")

    eventos = _eventos_mapa_territorial_pdf(request)
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
    doc = SimpleDocTemplate(response, pagesize=landscape(A4), rightMargin=10*mm, leftMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("TituloMapa", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17, leading=20, alignment=TA_CENTER, spaceAfter=3)
    comando = ParagraphStyle("ComandoMapa", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, alignment=TA_CENTER, spaceAfter=2)
    unidade = ParagraphStyle("UnidadeMapa", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=13, alignment=TA_CENTER, spaceAfter=3)
    subtitulo = ParagraphStyle("SubtituloMapa", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=3)
    periodo = ParagraphStyle("PeriodoMapa", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#444444"), spaceAfter=8)
    celula = ParagraphStyle("CelulaMapa", parent=styles["Normal"], fontSize=7, leading=8.2)
    cabecalho = ParagraphStyle("CabecalhoMapa", parent=celula, fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER)
    story = []
    logo_path = finders.find("logos/logo_pmba.png")
    if logo_path:
        logo = Image(logo_path, width=18*mm, height=18*mm); logo.hAlign = "CENTER"; story += [logo, Spacer(1, 1.5*mm)]
    story.append(Paragraph("POLÍCIA MILITAR DA BAHIA", titulo))
    story.append(Paragraph("COMANDO DE OPERAÇÕES POLICIAIS MILITARES", comando))
    story.append(Paragraph(_unidade_titulo(request, eventos), unidade))
    story.append(Paragraph("MAPA DE EVENTO", subtitulo))
    if data_inicio and data_fim:
        periodo_texto = f"Período: {datetime.strptime(data_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')} a {datetime.strptime(data_fim, '%Y-%m-%d').strftime('%d/%m/%Y')}"
    elif data_inicio:
        periodo_texto = f"A partir de {datetime.strptime(data_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')}"
    elif data_fim:
        periodo_texto = f"Até {datetime.strptime(data_fim, '%Y-%m-%d').strftime('%d/%m/%Y')}"
    else:
        periodo_texto = "Todos os eventos do âmbito institucional"
    story.append(Paragraph(periodo_texto, periodo))
    rows = [[Paragraph("DATA", cabecalho), Paragraph("INÍCIO", cabecalho), Paragraph("FIM", cabecalho), Paragraph("EVENTO", cabecalho), Paragraph("MUNICÍPIO", cabecalho), Paragraph("UNIDADE", cabecalho), Paragraph("REGIME", cabecalho)]]
    for evento in eventos:
        rows.append([
            Paragraph(evento.data_evento.strftime("%d/%m/%Y"), celula),
            Paragraph(evento.hora_inicio.strftime("%H:%M") if evento.hora_inicio else "-", celula),
            Paragraph(evento.hora_fim.strftime("%H:%M") if evento.hora_fim else "-", celula),
            Paragraph(str(evento.nome_evento or "-").upper(), celula),
            Paragraph(str(evento.municipio.nome if evento.municipio else "-").upper(), celula),
            Paragraph(str(evento.unidade.nome if evento.unidade else "-").upper(), celula),
            Paragraph(str(_tipo_opo_mapa(evento)).upper(), celula),
        ])
    tabela = Table(rows, repeatRows=1, colWidths=[24*mm,22*mm,22*mm,58*mm,40*mm,82*mm,36*mm], hAlign="CENTER")
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4b5563")),
        ("GRID", (0,0), (-1,-1), .45, colors.HexColor("#9ca3af")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(tabela)
    story.append(Spacer(1,4*mm))
    story.append(Paragraph("POLÍCIA MILITAR DA BAHIA - Sistema Integrado de Eventos", periodo))
    doc.build(story)
    return response
