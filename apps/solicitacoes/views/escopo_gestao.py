from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import AnexoOPO, DocumentoSolicitacao, Solicitacao, TipoDocumento
from apps.solicitacoes.pdf_security import validar_pdf_upload
from apps.solicitacoes.permissoes import (
    eh_desenvolvedor, eh_gestor, eh_operador, pode_gerar_opo,
    pode_ver_solicitacao, pode_ver_documentacao_solicitacao,
    pode_ver_mapa_eventos, escopo_unidades,
)
from .operacional import gerar_mapa_eventos_pdf as mapa_pdf_original
from .geracao_opo import gerar_opo_com_evento_extra


def _abrir_pdf_seguro(arquivo_field):
    if not arquivo_field:
        raise Http404("Documento sem arquivo associado.")
    nome = getattr(arquivo_field, "name", "") or ""
    if not nome:
        raise Http404("Documento sem nome de arquivo.")
    try:
        if default_storage.exists(nome):
            return default_storage.open(nome, "rb")
    except (OSError, ValueError):
        pass
    try:
        caminho = Path(settings.MEDIA_ROOT) / nome
        if caminho.is_file():
            return caminho.open("rb")
    except (OSError, ValueError):
        pass
    raise Http404(f"O PDF não foi encontrado no armazenamento. Arquivo registrado: {nome}")


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
    pode_anexar = s.status != "PENDENTE" and (eh_desenvolvedor(request.user) or (eh_gestor(request.user) and getattr(request.user.acesso_institucional, "perfil", None) == "UNIDADE"))
    if request.method == "POST":
        if not pode_anexar:
            messages.error(request, "A documentação desta solicitação já está encerrada nesta fase.")
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
    return render(request, "gestao/documentos_solicitacao.html", {"solicitacao": s, "documentos": docs, "tipos_documento": tipos, "pode_anexar": pode_anexar})


@login_required
def abrir_oficio_comandante_seguro(request, id):
    s = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)
    if not pode_ver_documentacao_solicitacao(request.user) or not pode_ver_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a este documento.")
        return redirect("painel_gestao")
    arquivo = _abrir_pdf_seguro(s.oficio_comandante)
    nome = Path(s.oficio_comandante.name).name or "oficio_comandante.pdf"
    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@login_required
def abrir_documento_solicitacao_seguro(request, id, tipo="arquivo"):
    doc = get_object_or_404(DocumentoSolicitacao.objects.select_related("solicitacao__unidade"), pk=id)
    if tipo not in {"pdf", "arquivo", "documento", "oficio_comandante"}:
        raise Http404("Tipo de documento inválido.")
    if not pode_ver_documentacao_solicitacao(request.user) or not pode_ver_solicitacao(request.user, doc.solicitacao):
        messages.error(request, "Você não possui acesso a este documento.")
        return redirect("painel_gestao")
    arquivo = _abrir_pdf_seguro(doc.arquivo)
    resposta = FileResponse(arquivo, content_type="application/pdf")
    nome = Path(doc.arquivo.name).name or "documento.pdf"
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@login_required
def abrir_opo_gestao_seguro(request, anexo_id):
    anexo = get_object_or_404(
        AnexoOPO.objects.select_related("solicitacao", "solicitacao__unidade"),
        pk=anexo_id,
    )
    solicitacao = anexo.solicitacao
    if eh_operador(request.user) or not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta OPO.")
        return redirect("painel_gestao")
    arquivo = _abrir_pdf_seguro(anexo.arquivo)
    nome = Path(anexo.arquivo.name).name or f"OPO_{solicitacao.protocolo}.pdf"
    resposta = FileResponse(arquivo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


@login_required
def opos_geradas_seguro(request):
    if eh_operador(request.user):
        messages.error(request, "Operadores só podem visualizar as OPOs liberadas em Eventos do Dia.")
        return redirect("eventos_dia")
    anexos = AnexoOPO.objects.select_related("solicitacao", "solicitacao__unidade", "solicitacao__municipio", "solicitacao__bairro").filter(solicitacao__unidade__in=escopo_unidades(request.user)).exclude(arquivo="").order_by("-criado_em")
    grupos = {}
    for a in anexos:
        if a.solicitacao.protocolo not in grupos:
            grupos[a.solicitacao.protocolo] = {"codigo": a.solicitacao.protocolo, "solicitacao": a.solicitacao, "arquivos": [], "documentos": list(DocumentoSolicitacao.objects.filter(solicitacao=a.solicitacao).select_related("tipo_documento"))}
        grupos[a.solicitacao.protocolo]["arquivos"].append(a)
    return render(request, "gestao/opos_geradas.html", {"protocolos": list(grupos.values()), "pode_apoio": eh_desenvolvedor(request.user) or eh_gestor(request.user)})


@login_required
def detalhe_opo_seguro(request, id):
    if eh_operador(request.user):
        messages.error(request, "Operadores só podem visualizar as OPOs liberadas em Eventos do Dia.")
        return redirect("eventos_dia")
    s = get_object_or_404(Solicitacao.objects.select_related("municipio", "bairro", "unidade", "tipo_evento"), pk=id)
    if not pode_ver_solicitacao(request.user, s):
        messages.error(request, "Você não possui acesso a esta OPO.")
        return redirect("painel_gestao")
    anexos = AnexoOPO.objects.filter(solicitacao=s).exclude(arquivo="").order_by("-criado_em")
    documentos = DocumentoSolicitacao.objects.filter(solicitacao=s).select_related("tipo_documento")
    a = getattr(request.user, "acesso_institucional", None)
    pode_apoio = bool(anexos.exists() and (eh_desenvolvedor(request.user) or (a and a.ativo and request.user.is_active and a.funcao == "GESTOR" and a.perfil in {"COPPM", "CPR", "UNIDADE"} and (a.perfil in {"COPPM", "CPR"} or a.unidade_id == s.unidade_id))))
    return render(request, "gestao/detalhe_opo.html", {"solicitacao": s, "anexos": anexos, "documentos": documentos, "pode_apoio": pode_apoio})


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
