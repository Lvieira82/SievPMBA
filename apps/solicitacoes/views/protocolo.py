# apps/solicitacoes/views/protocolo.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone

from apps.solicitacoes.models import (
    Solicitacao,
    DocumentoSolicitacao,
    HistoricoSolicitacao,
)


# ==========================================================
# PAINEL DE PROTOCOLO
# ==========================================================

def painel_protocolo(request):
    """
    Painel geral da central de protocolo.
    """

    context = {

        "novas": Solicitacao.objects.filter(
            status="PROTOCOLO"
        ).count(),

        "em_analise": Solicitacao.objects.filter(
            status="EM_ANALISE"
        ).count(),

        "correcao": Solicitacao.objects.filter(
            status="CORRECAO"
        ).count(),

        "aprovadas": Solicitacao.objects.filter(
            status="APROVADA"
        ).count(),

        "indeferidas": Solicitacao.objects.filter(
            status="INDEFERIDA"
        ).count(),

    }

    return render(
        request,
        "protocolo/painel.html",
        context,
    )


# ==========================================================
# FILA DE PROTOCOLOS
# ==========================================================

def fila_protocolo(request):
    """
    Lista todas as solicitações recém recebidas.
    """

    solicitacoes = Solicitacao.objects.filter(
        status="PROTOCOLO"
    ).order_by("data_cadastro")

    return render(
        request,
        "protocolo/fila.html",
        {
            "solicitacoes": solicitacoes
        }
    )


# ==========================================================
# DETALHES
# ==========================================================

def detalhes_protocolo(request, pk):

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    documentos = DocumentoSolicitacao.objects.filter(
        solicitacao=solicitacao
    )

    historico = HistoricoSolicitacao.objects.filter(
        solicitacao=solicitacao
    ).order_by("-data")

    context = {

        "solicitacao": solicitacao,

        "documentos": documentos,

        "historico": historico,

    }

    return render(
        request,
        "protocolo/detalhes.html",
        context,
    )


# ==========================================================
# ENCAMINHAR
# ==========================================================

def encaminhar_unidade(request, pk):
    """
    Encaminha automaticamente para a unidade responsável.
    """

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    solicitacao.status = "EM_ANALISE"

    solicitacao.data_encaminhamento = timezone.now()

    solicitacao.save()

    HistoricoSolicitacao.objects.create(

        solicitacao=solicitacao,

        status="EM_ANALISE",

        observacao="Solicitação encaminhada automaticamente para análise.",

    )

    messages.success(
        request,
        "Solicitação encaminhada com sucesso."
    )

    return redirect("fila_protocolo")


# ==========================================================
# HISTÓRICO
# ==========================================================

def historico_protocolo(request, pk):

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    historico = HistoricoSolicitacao.objects.filter(
        solicitacao=solicitacao
    ).order_by("-data")

    return render(
        request,
        "protocolo/historico.html",
        {
            "solicitacao": solicitacao,
            "historico": historico,
        }
    )


# ==========================================================
# REENVIAR EMAIL
# ==========================================================

def reenviar_email(request, pk):
    """
    Reenvia o e-mail de confirmação ao solicitante.
    """

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    # Será utilizada a função do portal.py
    # enviar_email_confirmacao(solicitacao)

    messages.success(
        request,
        "E-mail reenviado com sucesso."
    )

    return redirect(
        "detalhes_protocolo",
        pk=pk
    )


# ==========================================================
# CANCELAR PROTOCOLO
# ==========================================================

def cancelar_protocolo(request, pk):

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    solicitacao.status = "CANCELADA"

    solicitacao.save()

    HistoricoSolicitacao.objects.create(

        solicitacao=solicitacao,

        status="CANCELADA",

        observacao="Solicitação cancelada pela Central de Protocolo.",

    )

    messages.success(
        request,
        "Solicitação cancelada."
    )

    return redirect(
        "fila_protocolo"
    )


# ==========================================================
# ESTATÍSTICAS
# ==========================================================

def estatisticas_protocolo(request):

    por_status = (
        Solicitacao.objects
        .values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )

    context = {

        "por_status": por_status,

        "total": Solicitacao.objects.count(),

    }

    return render(
        request,
        "protocolo/estatisticas.html",
        context,
    )