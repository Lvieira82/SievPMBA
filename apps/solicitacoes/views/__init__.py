"""
Camada de compatibilidade entre o SiEv antigo
e a arquitetura modular PMBA.

Não apagar este arquivo.
"""

# ==========================================
# IMPORTA TODAS AS VIEWS NOVAS
# ==========================================
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.models import User
from apps.solicitacoes.models import PerfilUsuario
from django.shortcuts import redirect
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


# ==========================================
# PLACEHOLDERS
# Implementar posteriormente
# ==========================================

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


def documentos_solicitacao(request, *args, **kwargs):
    return HttpResponse(
        "Função documentos_solicitacao ainda não implementada."
    )


def abrir_documento_solicitacao(request, *args, **kwargs):
    return HttpResponse(
        "Função abrir_documento_solicitacao ainda não implementada."
    )


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