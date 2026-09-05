from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.files.storage import default_storage

from apps.solicitacoes.models import AnexoOPO, DocumentoSolicitacao, Solicitacao, TipoDocumento
from apps.solicitacoes.pdf_security import validar_pdf_upload
from apps.solicitacoes.permissoes import (
    eh_desenvolvedor,
    eh_gestor,
    eh_operador,
    pode_gerar_opo,
    pode_ver_solicitacao,
    pode_ver_documentacao_solicitacao,
    pode_ver_mapa_eventos,
    escopo_unidades,
)
from .operacional import gerar_mapa_eventos_pdf as mapa_pdf_original
from .geracao_opo import gerar_opo_com_evento_extra


@login_required
def documentos_solicitacao_seguro(request, id):
    s = get_object_or_404(Solicitacao.objects.select_related("unidade", "municipio", "bairro"), pk=id)
    if not pode_ver_documentacao_solicitacao(request.user):
        messages.error(request, "A documentação das solicitações é exclusiva do Gestor de Unidade e do Desenvolvedor.")
        return redirect("painel_gestao")
    if not pode_ver_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso aos documentos desta solicitação.")
        return redirect("painel_gestao")

    docs = DocumentoSolicitacao.objects.filter(solicitacao=s).select_related("tipo_documento")
    tipos = TipoDocumento.objects.filter(ativo=True).order_by("nome")
    if request.method == "POST":
        if not (eh_desenvolvedor(request.user) or (eh_gestor(request.user) and getattr(request.user.acesso_institucional, "perfil", None) == "UNIDADE")):
            messages.error(request, "Você não possui permissão para anexar documentos.")
            return redirect("documentos_solicitacao", id=id)
        arq = request.FILES.get("arquivo")
        tid = request.POST.get("tipo_documento")
        if not arq or not tid:
            messages.error(request, "Informe o PDF e o tipo do documento.")
        else:
            try:
                validar_pdf_upload(arq)
                tipo = get_object_or_404(TipoDocumento, pk=tid, ativo=True)
                DocumentoSolicitacao.objects.create(solicitacao=s, tipo_documento=tipo, descricao=request.POST.get("descricao", "").strip(), arquivo=arq)
                messages.success(request, "Documento anexado com sucesso.")
                return redirect("documentos_solicitacao", id=id)
            except Exception as e:
                messages.error(request, f"Documento rejeitado: {e}")
    return render(request, "gestao/documentos_solicitacao.html", {"solicitacao": s, "documentos": docs, "tipos_documento": tipos})


@login_required
def abrir_documento_solicitacao_seguro(request, id, tipo):
    doc = get_object_or_404(DocumentoSolicitacao.objects.select_related("solicitacao__unidade"), pk=id)
    if tipo not in {"pdf", "arquivo"} or not doc.arquivo:
        raise Http404("Arquivo não encontrado.")
    if not pode_ver_documentacao_solicitacao(request.user) or not pode_ver_solicitacao(request.user, doc.solicitacao):
        messages.error(request, "Você não possui acesso a este documento.")
        return redirect("painel_gestao")
    try:
        nome = doc.arquivo.name
        if not nome or not default_storage.exists(nome):
            raise Http404("O arquivo não está disponível no armazenamento do SiEv.")
        arquivo = default_storage.open(nome, "rb")
    except FileNotFoundError:
        raise Http404("O arquivo não está disponível no armazenamento do SiEv.")
    except OSError:
        raise Http404("Não foi possível abrir o arquivo PDF.")
    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = "inline"
    return resposta


@login_required
def opos_geradas_seguro(request):
    if eh_operador(request.user):
        messages.error(request, "Operadores só podem visualizar as OPOs liberadas em Eventos do Dia.")
        return redirect("eventos_dia")
    anexos = AnexoOPO.objects.select_related(
        "solicitacao", "solicitacao__unidade", "solicitacao__municipio", "solicitacao__bairro"
    ).filter(solicitacao__unidade__in=escopo_unidades(request.user)).order_by("-criado_em")
    grupos = {}
    for a in anexos:
        grupos.setdefault(a.solicitacao.protocolo, {"codigo": a.solicitacao.protocolo, "solicitacao": a.solicitacao, "arquivos": []})["arquivos"].append(a)
    return render(request, "gestao/opos_geradas.html", {"protocolos": list(grupos.values())})


@login_required
def detalhe_opo_seguro(request, id):
    if eh_operador(request.user):
        messages.error(request, "Operadores só podem visualizar as OPOs liberadas em Eventos do Dia.")
        return redirect("eventos_dia")
    s = get_object_or_404(Solicitacao.objects.select_related("municipio", "bairro", "unidade", "tipo_evento"), pk=id)
    if not pode_ver_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a esta OPO.")
        return redirect("painel_gestao")
    return render(request, "gestao/detalhe_opo.html", {"solicitacao": s, "anexos": AnexoOPO.objects.filter(solicitacao=s).order_by("-criado_em")})


@login_required
def gerar_opo_seguro(request, id):
    s = get_object_or_404(Solicitacao, pk=id)
    if not pode_gerar_opo(request.user, s):
        messages.error(request, "Você não possui permissão para gerar esta OPO.")
        return redirect("painel_gestao")
    return gerar_opo_com_evento_extra(request, id)


@login_required
def mapa_eventos_seguro(request):
    if not pode_ver_mapa_eventos(request.user):
        messages.error(request, "O mapa de eventos está disponível para gestores de CPR e Unidade.")
        return redirect("painel_gestao")
    eventos = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user), data_evento__gte=timezone.localdate()).select_related("municipio", "bairro", "unidade").order_by("data_evento", "hora_inicio")
    return render(request, "gestao/mapa_eventos.html", {"eventos": eventos})


@login_required
def gerar_mapa_eventos_pdf_seguro(request):
    if not pode_ver_mapa_eventos(request.user):
        messages.error(request, "O mapa de eventos está disponível para gestores de CPR e Unidade.")
        return redirect("painel_gestao")
    return mapa_pdf_original(request)
