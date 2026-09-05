import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from apps.solicitacoes.models import AnexoOPO, HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.permissoes import pode_gerar_opo


def _pdf_opo(solicitacao, evento_extra=False):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=38, leftMargin=38, topMargin=38, bottomMargin=38)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("opo_titulo", parent=styles["Title"], alignment=TA_CENTER, fontSize=15, leading=18, spaceAfter=16)
    normal = ParagraphStyle("opo_normal", parent=styles["Normal"], fontSize=10, leading=14)
    story = [
        Paragraph("POLÍCIA MILITAR DA BAHIA", titulo),
        Paragraph("RECOMENDO EXECUTARDES A SEGUINTE OPO:", titulo),
    ]

    efetivo = "Efetivo extraordinário escalado." if evento_extra else "01 (uma) Guarnição a critério do Coordenador de Área."
    observacoes = solicitacao.observacoes or ""
    if not observacoes:
        observacoes = "O organizador do evento está ciente de que caso haja perturbação do sossego, aglomeração ou outro tipo de infração, a guarnição adotará as medidas cabíveis."

    dados = [
        ["EVENTO:", solicitacao.nome_evento],
        ["LOCAL:", solicitacao.local],
        ["DATA:", solicitacao.data_evento.strftime("%d/%m/%Y")],
        ["HORÁRIO:", f"{solicitacao.hora_inicio:%H:%M} – {solicitacao.hora_fim:%H:%M}"],
        ["EFETIVO:", efetivo],
        ["UNIFORME E ARMAMENTO:", "O de Dotação desta UOPM"],
        ["SOLICITANTE:", f"{solicitacao.solicitante} ({solicitacao.telefone})"],
        ["OBSERVAÇÕES:", observacoes],
    ]
    tabela = Table([[Paragraph(str(a), normal), Paragraph(str(b), normal)] for a, b in dados], colWidths=[145, 370])
    tabela.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 22))
    story.append(Paragraph("Ordem de policiamento gerada por", normal))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>SiEv – Sistema Integrado de Eventos</b>", normal))
    story.append(Spacer(1, 14))
    story.append(Paragraph(f"Protocolo: {solicitacao.protocolo}", normal))
    doc.build(story)
    return buffer.getvalue()


@login_required
def gerar_opo_com_evento_extra(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade", "municipio", "bairro"), pk=id)

    if not pode_gerar_opo(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para gerar esta OPO.")
        return redirect("painel_gestao")

    if solicitacao.status not in {"APROVADA", "CONCLUIDA"}:
        messages.error(request, "A OPO somente pode ser gerada após a aprovação da solicitação.")
        return redirect("aprovacoes")

    if not solicitacao.documentos.exists():
        messages.error(request, "A OPO não pode ser gerada sem documentos anexados.")
        return redirect("aprovacoes")

    if request.method == "GET":
        return render(request, "gestao/gerar_opo.html", {"solicitacao": solicitacao})

    evento_extra = request.POST.get("evento_extra") == "SIM"
    conteudo = _pdf_opo(solicitacao, evento_extra=evento_extra)
    nome = f"OPO_{solicitacao.protocolo}.pdf"
    anexo = AnexoOPO.objects.create(solicitacao=solicitacao, descricao=f"OPO gerada pelo SiEv — Evento extra: {'SIM' if evento_extra else 'NÃO'}")
    anexo.arquivo.save(nome, ContentFile(conteudo), save=True)

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="OPO GERADA",
        detalhes=f"Arquivo {nome} gerado. Evento extra: {'SIM' if evento_extra else 'NÃO'}.",
    )
    messages.success(request, f"OPO {solicitacao.protocolo} gerada com sucesso.")
    return redirect("detalhe_opo", id=id)
