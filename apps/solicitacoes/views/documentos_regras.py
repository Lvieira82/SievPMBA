"""Regras de documentos para aprovação e geração de OPO."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from apps.solicitacoes.models import (
    ConfiguracaoUnidade,
    DocumentoSolicitacao,
    Solicitacao,
)
from .administracao import aprovar_solicitacao, solicitar_correcao_gestao
from .operacional import gerar_opo


def documentos_pendentes(solicitacao):
    """
    Retorna os motivos que impedem a aprovação/geração da OPO.

    Regra mínima: deve existir pelo menos um documento anexado.
    Regra complementar: todos os tipos configurados como obrigatórios
    para a unidade da solicitação devem estar anexados.
    """
    pendentes = []

    documentos = DocumentoSolicitacao.objects.filter(
        solicitacao=solicitacao
    )

    if not documentos.exists():
        pendentes.append("Nenhum documento foi anexado.")
        return pendentes

    tipos_anexados = set(
        documentos.values_list("tipo_documento_id", flat=True)
    )

    configuracoes = ConfiguracaoUnidade.objects.filter(
        unidade=solicitacao.unidade,
        ativo=True,
        obrigatorio=True,
        tipo_documento__isnull=False,
    ).select_related("tipo_documento")

    tipos_obrigatorios = {}
    for configuracao in configuracoes:
        tipos_obrigatorios[configuracao.tipo_documento_id] = (
            configuracao.tipo_documento.nome
        )

    faltantes = [
        nome
        for tipo_id, nome in tipos_obrigatorios.items()
        if tipo_id not in tipos_anexados
    ]

    if faltantes:
        pendentes.append(
            "Documentos obrigatórios ausentes: " + ", ".join(faltantes) + "."
        )

    return pendentes


@login_required
def aprovar_com_validacao_documentos(request, id):
    solicitacao = get_object_or_404(Solicitacao, pk=id)

    if request.method == "POST":
        pendentes = documentos_pendentes(solicitacao)
        if pendentes:
            for mensagem in pendentes:
                messages.error(request, mensagem)
            messages.warning(
                request,
                "A solicitação somente pode ser aprovada depois da conferência dos documentos."
            )
            return redirect("documentos_solicitacao", id=id)

    return aprovar_solicitacao(request, id)


@login_required
def corrigir_com_validacao_documentos(request, id):
    solicitacao = get_object_or_404(Solicitacao, pk=id)

    if request.method == "POST":
        pendentes = documentos_pendentes(solicitacao)
        if pendentes:
            for mensagem in pendentes:
                messages.error(request, mensagem)
            messages.warning(
                request,
                "A solicitação somente pode ser enviada para correção depois da conferência dos documentos."
            )
            return redirect("documentos_solicitacao", id=id)

    return solicitar_correcao_gestao(request, id)


@login_required
def gerar_opo_com_validacao_documentos(request, id):
    solicitacao = get_object_or_404(Solicitacao, pk=id)

    pendentes = documentos_pendentes(solicitacao)
    if pendentes:
        for mensagem in pendentes:
            messages.error(request, mensagem)
        messages.warning(
            request,
            "A OPO não pode ser gerada enquanto os documentos necessários não estiverem conferidos."
        )
        return redirect("documentos_solicitacao", id=id)

    return gerar_opo(request, id)
