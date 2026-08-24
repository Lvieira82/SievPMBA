# apps/solicitacoes/views/analise.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count

from apps.solicitacoes.models import (
    Solicitacao,
    DocumentoSolicitacao,
    HistoricoSolicitacao,
)


# ==========================================================
# PAINEL DA UNIDADE
# ==========================================================

@login_required
def painel_analise(request):

    context = {

        "novas": Solicitacao.objects.filter(status="EM_ANALISE").count(),

        "correcao": Solicitacao.objects.filter(status="CORRECAO").count(),

        "aprovadas": Solicitacao.objects.filter(status="APROVADA").count(),

        "indeferidas": Solicitacao.objects.filter(status="INDEFERIDA").count(),

    }

    return render(
        request,
        "analise/painel.html",
        context,
    )


# ==========================================================
# FILA DA UNIDADE
# ==========================================================

@login_required
def fila_analise(request):

    solicitacoes = Solicitacao.objects.filter(
        status="EM_ANALISE"
    ).order_by("data_evento")

    return render(
        request,
        "analise/fila.html",
        {
            "solicitacoes": solicitacoes
        }
    )


# ==========================================================
# DETALHES
# ==========================================================

@login_required
def detalhes(request, pk):

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

    return render(
        request,
        "analise/detalhes.html",
        {

            "solicitacao": solicitacao,

            "documentos": documentos,

            "historico": historico,

        }
    )


# ==========================================================
# APROVAR
# ==========================================================

@login_required
def aprovar(request, pk):

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()

    solicitacao.save()

    HistoricoSolicitacao.objects.create(

        solicitacao=solicitacao,

        status="APROVADA",

        usuario=request.user,

        descricao="Solicitação aprovada.",

    )

    messages.success(
        request,
        "Solicitação aprovada com sucesso."
    )

    return redirect("fila_analise")


# ==========================================================
# SOLICITAR CORREÇÃO
# ==========================================================

@login_required
def solicitar_correcao(request, pk):

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    if request.method == "POST":

        motivo = request.POST.get("motivo", "").strip()

        if not motivo:

            messages.error(
                request,
                "Informe o motivo da correção."
            )

            return redirect("detalhes", pk=pk)

        solicitacao.status = "CORRECAO"

        solicitacao.save()

        HistoricoSolicitacao.objects.create(

            solicitacao=solicitacao,

            status="CORRECAO",

            usuario=request.user,

            descricao=motivo,

        )

        messages.success(
            request,
            "Correção solicitada."
        )

    return redirect("fila_analise")


# ==========================================================
# INDEFERIR
# ==========================================================

@login_required
def indeferir(request, pk):

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    if request.method == "POST":

        motivo = request.POST.get("motivo", "").strip()

        if not motivo:

            messages.error(
                request,
                "Informe o motivo do indeferimento."
            )

            return redirect("detalhes", pk=pk)

        solicitacao.status = "INDEFERIDA"

        solicitacao.save()

        HistoricoSolicitacao.objects.create(

            solicitacao=solicitacao,

            status="INDEFERIDA",

            usuario=request.user,

            descricao=motivo,

        )

        messages.success(
            request,
            "Solicitação indeferida."
        )

    return redirect("fila_analise")


# ==========================================================
# HISTÓRICO
# ==========================================================

@login_required
def historico(request, pk):

    solicitacao = get_object_or_404(
        Solicitacao,
        pk=pk
    )

    historico = HistoricoSolicitacao.objects.filter(
        solicitacao=solicitacao
    ).order_by("-data")

    return render(
        request,
        "analise/historico.html",
        {

            "solicitacao": solicitacao,

            "historico": historico,

        }
    )


# ==========================================================
# ESTATÍSTICAS
# ==========================================================

@login_required
def estatisticas(request):

    dados = (

        Solicitacao.objects

        .values("status")

        .annotate(total=Count("id"))

        .order_by("status")

    )

    return render(
        request,
        "analise/estatisticas.html",
        {

            "dados": dados,

            "total": Solicitacao.objects.count(),

        }
    )