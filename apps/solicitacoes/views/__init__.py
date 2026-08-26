"""
Camada de compatibilidade entre o SiEv antigo
e a arquitetura modular PMBA.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from apps.solicitacoes.models import (
    PerfilUsuario,
    Solicitacao,
    DocumentoSolicitacao,
)

from .portal import *
from .dashboard import *
from .analise import *
from .protocolo import *
from .administracao import *


# ==========================================
# COMPATIBILIDADE
# ==========================================

def minhas_solicitacoes(request):
    return redirect("consultar")


def verificar_autenticidade(request, *args, **kwargs):
    return HttpResponse(
        "Função verificar_autenticidade ainda não implementada."
    )


def alterar_status(request, *args, **kwargs):
    return HttpResponse(
        "Função alterar_status ainda não implementada."
    )


def listar_pendentes_opo(request, *args, **kwargs):
    return HttpResponse(
        "Função listar_pendentes_opo ainda não implementada."
    )


# ==========================================
# DOCUMENTOS DA SOLICITAÇÃO
# ==========================================

def _gestor_pode_ver_solicitacao(request, solicitacao):
    """
    Restringe os documentos exatamente à área institucional do usuário.

    Desenvolvedor/administrador: acesso total.
    COPPM: toda a PMBA.
    CPR: apenas unidades subordinadas ao seu CPR.
    UNIDADE: apenas sua própria unidade.
    """

    usuario = request.user

    if usuario.is_superuser or usuario.is_staff:
        return True

    perfil = getattr(usuario, "perfil_siev", None)

    if not perfil or not perfil.ativo:
        return False

    if perfil.perfil == "COPPM":
        return True

    if perfil.perfil == "CPR":
        return bool(
            perfil.cpr
            and solicitacao.unidade
            and solicitacao.unidade.cpr_id == perfil.cpr_id
        )

    if perfil.perfil == "UNIDADE":
        return bool(
            perfil.unidade
            and solicitacao.unidade_id == perfil.unidade_id
        )

    return False


@login_required
def documentos_solicitacao(request, id):
    """
    Exibe os documentos efetivamente anexados à solicitação.

    Esta view consulta DocumentoSolicitacao diretamente no banco, em vez
    de montar uma lista de documentos esperados. Assim, tudo que foi
    anexado pelo solicitante aparece para a gestão.
    """

    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related(
            "unidade",
            "unidade__cpr",
        ),
        pk=id,
    )

    if not _gestor_pode_ver_solicitacao(request, solicitacao):
        messages.error(
            request,
            "Você não possui permissão para visualizar os documentos desta solicitação."
        )
        return redirect("painel_gestao")

    documentos = (
        DocumentoSolicitacao.objects
        .filter(solicitacao=solicitacao)
        .select_related("tipo_documento")
        .order_by("tipo_documento__nome", "id")
    )

    return render(
        request,
        "gestao/documentos_solicitacao.html",
        {
            "solicitacao": solicitacao,
            "documentos": documentos,
            "tem_documentos": documentos.exists(),
        },
    )


@login_required
def abrir_documento_solicitacao(request, id, tipo):
    """
    Abre um PDF anexado somente para um usuário institucional autorizado.
    """

    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related(
            "unidade",
            "unidade__cpr",
        ),
        pk=id,
    )

    if not _gestor_pode_ver_solicitacao(request, solicitacao):
        messages.error(
            request,
            "Você não possui permissão para abrir este documento."
        )
        return redirect("painel_gestao")

    documento = get_object_or_404(
        DocumentoSolicitacao.objects.select_related("tipo_documento"),
        solicitacao=solicitacao,
        tipo_documento__nome=tipo,
    )

    if not documento.arquivo:
        raise Http404("Documento não possui arquivo anexado.")

    try:
        arquivo = documento.arquivo.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("Arquivo do documento não encontrado.")

    resposta = FileResponse(
        arquivo,
        content_type="application/pdf",
    )
    resposta["Content-Disposition"] = (
        f'inline; filename="{documento.arquivo.name.rsplit("/", 1)[-1]}"'
    )
    return resposta


# ==========================================
# PLACEHOLDERS
# ==========================================

def agenda_gestao(request, *args, **kwargs):
    return HttpResponse(
        "Função agenda_gestao ainda não implementada."
    )


def lancamento_manual(request, *args, **kwargs):
    return HttpResponse(
        "Função lancamento_manual ainda não implementada."
    )


def opos_geradas(request, *args, **kwargs):
    return HttpResponse(
        "Função opos_geradas ainda não implementada."
    )


def detalhe_opo(request, *args, **kwargs):
    return HttpResponse(
        "Função detalhe_opo ainda não implementada."
    )


def gerar_opo(request, *args, **kwargs):
    return HttpResponse(
        "Função gerar_opo ainda não implementada."
    )


def validar_matricula_opo_publica(request, *args, **kwargs):
    return HttpResponse(
        "Função validar_matricula_opo_publica ainda não implementada."
    )


def detalhe_opo_publica(request, *args, **kwargs):
    return HttpResponse(
        "Função detalhe_opo_publica ainda não implementada."
    )


def importar_matriculas_painel(request, *args, **kwargs):
    return HttpResponse(
        "Função importar_matriculas_painel ainda não implementada."
    )


def corrigir_solicitacao(request, *args, **kwargs):
    return HttpResponse(
        "Função corrigir_solicitacao ainda não implementada."
    )


def mapa_eventos(request, *args, **kwargs):
    return HttpResponse(
        "Função mapa_eventos ainda não implementada."
    )


def gerar_mapa_eventos_pdf(request, *args, **kwargs):
    return HttpResponse(
        "Função gerar_mapa_eventos_pdf ainda não implementada."
    )


def importar_municipios(request, *args, **kwargs):
    return HttpResponse(
        "Função importar_municipios ainda não implementada."
    )
