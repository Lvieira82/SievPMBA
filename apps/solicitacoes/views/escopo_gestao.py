import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import AnexoOPO, DocumentoSolicitacao, Solicitacao, TipoDocumento
from apps.solicitacoes.pdf_security import validar_pdf_upload
from apps.solicitacoes.permissoes import eh_desenvolvedor, eh_gestor, pode_ver_solicitacao, escopo_unidades
from .operacional import gerar_mapa_eventos_pdf as gerar_mapa_eventos_pdf_original


@login_required
def documentos_solicitacao_seguro(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade", "municipio", "bairro"), pk=id)
    if not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso aos documentos desta solicitação.")
        return redirect("painel_gestao")

    documentos = DocumentoSolicitacao.objects.filter(solicitacao=solicitacao).select_related("tipo_documento")
    tipos = TipoDocumento.objects.filter(ativo=True).order_by("nome")

    if request.method == "POST":
        if not (eh_desenvolvedor(request.user) or eh_gestor(request.user)):
            messages.error(request, "Somente gestores podem anexar documentos nesta área.")
            return redirect("documentos_solicitacao", id=id)

        arquivo = request.FILES.get("arquivo")
        tipo_id = request.POST.get("tipo_documento")
        descricao = request.POST.get("descricao", "").strip()
        if not arquivo or not tipo_id:
            messages.error(request, "Informe o PDF e o tipo do documento.")
        else:
            try:
                validar_pdf_upload(arquivo)
                tipo = get_object_or_404(TipoDocumento, pk=tipo_id, ativo=True)
                DocumentoSolicitacao.objects.create(solicitacao=solicitacao, tipo_documento=tipo, descricao=descricao, arquivo=arquivo)
                messages.success(request, "Documento anexado com sucesso.")
                return redirect("documentos_solicitacao", id=id)
            except Exception as exc:
                messages.error(request, f"Documento rejeitado: {exc}")

    return render(request, "gestao/documentos_solicitacao.html", {
        "solicitacao": solicitacao, "documentos": documentos, "tipos_documento": tipos,
    })


@login_required
def opos_geradas_seguro(request):
    anexos = AnexoOPO.objects.select_related(
        "solicitacao", "solicitacao__unidade", "solicitacao__municipio", "solicitacao__bairro"
    ).filter(solicitacao__unidade__in=escopo_unidades(request.user)).order_by("-criado_em")

    agrupados = {}
    for anexo in anexos:
        codigo = anexo.solicitacao.protocolo
        agrupados.setdefault(codigo, {"codigo": codigo, "solicitacao": anexo.solicitacao, "arquivos": []})
        agrupados[codigo]["arquivos"].append(anexo)

    return render(request, "gestao/opos_geradas.html", {"protocolos": list(agrupados.values())})


@login_required
def detalhe_opo_seguro(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("municipio", "bairro", "unidade", "tipo_evento"), pk=id)
    if not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta OPO.")
        return redirect("painel_gestao")
    anexos = AnexoOPO.objects.filter(solicitacao=solicitacao).order_by("-criado_em")
    return render(request, "gestao/detalhe_opo.html", {"solicitacao": solicitacao, "anexos": anexos})


@login_required
def mapa_eventos_seguro(request):
    eventos = Solicitacao.objects.filter(
        unidade__in=escopo_unidades(request.user),
        data_evento__gte=timezone.localdate(),
    ).select_related("municipio", "bairro", "unidade").order_by("data_evento", "hora_inicio")
    return render(request, "gestao/mapa_eventos.html", {"eventos": eventos})


@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    eventos = Solicitacao.objects.filter(
        unidade__in=escopo_unidades(request.user),
        data_evento__gte=timezone.localdate(),
    ).select_related("municipio", "bairro", "unidade").order_by("data_evento", "hora_inicio")

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="mapa_eventos.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    rows = [["Data", "Hora", "Evento", "Município", "Unidade"]]
    for evento in eventos:
        rows.append([
            evento.data_evento.strftime("%d/%m/%Y"), evento.hora_inicio.strftime("%H:%M"),
            evento.nome_evento, evento.municipio.nome, evento.unidade.sigla if evento.unidade else "-",
        ])
    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#907C64")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    doc.build([Paragraph("MAPA DE EVENTOS - SiEv", styles["Title"]), Spacer(1, 12), table])
    return response
