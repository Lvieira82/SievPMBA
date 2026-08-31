"""Geração e verificação pública das Ordens de Policiamento (OPO)."""

import io
from xml.sax.saxutils import escape

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.solicitacoes.models import AnexoOPO, HistoricoSolicitacao, Solicitacao


def _texto(valor, padrao="-"):
    if valor is None:
        return padrao
    valor = str(valor).strip()
    return valor or padrao


def _url_verificacao(request, solicitacao):
    return request.build_absolute_uri(
        reverse("verificar_autenticidade", kwargs={"protocolo": solicitacao.protocolo})
    )


def _qr_code(url):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    imagem = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _gerar_pdf_opo(request, solicitacao):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=f"OPO {solicitacao.protocolo}",
        author="SiEv - Polícia Militar da Bahia",
    )

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("OpoTitulo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=17, alignment=TA_CENTER, spaceAfter=3)
    subtitulo = ParagraphStyle("OpoSubtitulo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=13, alignment=TA_CENTER, spaceAfter=2)
    pequeno_centro = ParagraphStyle("OpoCentro", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_CENTER)
    numero = ParagraphStyle("OpoNumero", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_CENTER, spaceBefore=10, spaceAfter=13)
    intro = ParagraphStyle("OpoIntro", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=TA_CENTER, spaceAfter=13)
    rotulo = ParagraphStyle("OpoRotulo", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=11)
    valor = ParagraphStyle("OpoValor", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=11)
    observacao = ParagraphStyle("OpoObservacao", parent=valor, spaceBefore=2, spaceAfter=5)
    rodape = ParagraphStyle("OpoRodape", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=10, alignment=TA_CENTER, spaceBefore=8)
    autenticidade = ParagraphStyle("OpoAutenticidade", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.HexColor("#333333"))
    aprovado = ParagraphStyle("OpoAprovado", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, alignment=TA_CENTER, spaceBefore=6)

    story = []

    try:
        from django.contrib.staticfiles import finders
        logo_path = finders.find("logos/logo_pmba.png")
    except Exception:
        logo_path = None

    if logo_path:
        logo = Image(logo_path)
        logo.drawHeight = 1.8 * cm
        logo.drawWidth = 1.8 * cm
        logo.hAlign = "CENTER"
        story.extend([logo, Spacer(1, 0.15 * cm)])

    unidade = getattr(solicitacao, "unidade", None)
    unidade_nome = _texto(getattr(unidade, "sigla", None) or getattr(unidade, "nome", None), "UNIDADE NÃO DEFINIDA")
    municipio = _texto(getattr(getattr(solicitacao, "municipio", None), "nome", None), "")

    story.append(Paragraph("POLÍCIA MILITAR DA BAHIA", titulo))
    story.append(Paragraph("COMANDO DE OPERAÇÕES POLICIAIS MILITARES", subtitulo))
    story.append(Paragraph(escape(unidade_nome) + (f" - {escape(municipio)}" if municipio else ""), pequeno_centro))

    data_geracao = timezone.localtime()
    story.append(Paragraph(
        f"OPO Nº {escape(_texto(solicitacao.protocolo))} - {data_geracao.strftime('%d/%m/%Y')}",
        numero,
    ))
    story.append(Paragraph("RECOMENDO EXECUTARDES A SEGUINTE OPO:", intro))

    def P(texto, style=valor):
        return Paragraph(escape(_texto(texto)), style)

    data_evento = solicitacao.data_evento.strftime("%d/%m/%Y") if solicitacao.data_evento else "-"
    horario = "-"
    if solicitacao.hora_inicio and solicitacao.hora_fim:
        horario = f"{solicitacao.hora_inicio.strftime('%H:%M')} - {solicitacao.hora_fim.strftime('%H:%M')}"

    dados = [
        [P("EVENTO:", rotulo), P(solicitacao.nome_evento)],
        [P("LOCAL:", rotulo), P(solicitacao.local)],
        [P("DATA:", rotulo), P(data_evento)],
        [P("HORÁRIO:", rotulo), P(horario)],
        [P("EFETIVO:", rotulo), P("01 (uma) Guarnição a critério do Coordenador de Área. Modalidade: Patrulhamento. Processo: Motorizado.")],
        [P("UNIFORME E ARMAMENTO:", rotulo), P("O de Dotação desta UOPM")],
        [P("SOLICITANTE:", rotulo), P(f"{_texto(solicitacao.solicitante)} {_texto(solicitacao.telefone)}")],
    ]

    tabela = Table(dados, colWidths=[4.0 * cm, 12.8 * cm], hAlign="CENTER")
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tabela)

    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("OBSERVAÇÕES:", rotulo))
    story.append(Paragraph("• O organizador do evento está ciente que caso haja perturbação do sossego, aglomeração ou outro tipo de infração, a guarnição adotará as medidas cabíveis.", observacao))
    story.append(Paragraph("• A viatura deve realizar Alfa 16 e no local, durante o evento.", observacao))
    story.append(Paragraph("• Constar o desenvolvimento desta OPO no relatório de serviço.", observacao))

    if _texto(solicitacao.observacoes, ""):
        story.append(Paragraph("OBSERVAÇÃO DA SOLICITAÇÃO:", rotulo))
        story.append(Paragraph(escape(_texto(solicitacao.observacoes, "")).replace("\n", "<br/>"), observacao))

    nome_aprovador = _texto(getattr(solicitacao, "aprovado_por", None), "Sistema SiEv")
    data_aprovacao = getattr(solicitacao, "data_aprovacao", None)
    data_aprovacao_texto = timezone.localtime(data_aprovacao).strftime("%d/%m/%Y %H:%M") if data_aprovacao else "-"

    story.append(Paragraph(f"APROVADO POR: {escape(nome_aprovador)}", aprovado))
    story.append(Paragraph(f"DATA DA APROVAÇÃO: {data_aprovacao_texto}", autenticidade))
    story.append(Paragraph("Ordem de policiamento gerada pelo SiEv.", rodape))

    url_verificacao = _url_verificacao(request, solicitacao)
    qr_buffer = _qr_code(url_verificacao)
    qr = Image(qr_buffer, width=2.6 * cm, height=2.6 * cm)
    qr.hAlign = "CENTER"
    story.append(Spacer(1, 0.1 * cm))
    story.append(qr)
    story.append(Paragraph("Verifique a autenticidade deste documento escaneando o QR Code ou acessando:", autenticidade))
    story.append(Paragraph(
        f'<link href="{escape(url_verificacao)}" color="#1e3a8a">{escape(url_verificacao)}</link>',
        autenticidade,
    ))

    doc.build(story)
    return buffer.getvalue()


@login_required
def gerar_opo(request, id):
    solicitacao = get_object_or_404(Solicitacao, pk=id)

    if solicitacao.status not in {"APROVADA", "CONCLUIDA"}:
        messages.error(request, "A OPO somente pode ser gerada após a aprovação da solicitação.")
        return redirect("listar_pendentes_opo")

    conteudo = _gerar_pdf_opo(request, solicitacao)
    nome = f"OPO_{solicitacao.protocolo}.pdf"
    anexo = AnexoOPO(solicitacao=solicitacao, descricao="OPO gerada pelo SiEv")
    anexo.arquivo.save(nome, ContentFile(conteudo), save=True)

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="OPO GERADA",
        observacao=f"Arquivo {nome} gerado pelo sistema.",
    )
    messages.success(request, "OPO gerada e arquivada no protocolo.")
    return redirect("detalhe_opo", id=id)


def verificar_autenticidade(request, protocolo):
    """Página pública usada pelo link e QR Code da OPO."""
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related("municipio", "unidade"),
        protocolo=protocolo,
    )
    return render(request, "gestao/verificar_autenticidade.html", {"solicitacao": solicitacao})
