from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db.models import Count

from apps.solicitacoes.models import (
    HistoricoSolicitacao,
    Solicitacao,
    TransferenciaSolicitacao,
    Unidade,
)


def _unidades_permitidas(request):
    perfil = getattr(request.user, "perfil_siev", None)
    if request.user.is_superuser or request.user.is_staff:
        return Unidade.objects.filter(ativo=True)
    if not perfil or not perfil.ativo:
        return Unidade.objects.none()
    if perfil.perfil == "COPPM":
        return Unidade.objects.filter(ativo=True)
    if perfil.perfil == "CPR" and perfil.cpr_id:
        return Unidade.objects.filter(cpr_id=perfil.cpr_id, ativo=True)
    if perfil.perfil == "UNIDADE" and perfil.unidade_id:
        return Unidade.objects.filter(pk=perfil.unidade_id, ativo=True)
    return Unidade.objects.none()


def _inicio_atendimento(solicitacao, unidade):
    """Define quando a solicitação chegou à unidade analisada."""
    transferencia = (
        TransferenciaSolicitacao.objects
        .filter(solicitacao=solicitacao, unidade_destino=unidade)
        .order_by("-criado_em")
        .first()
    )
    if transferencia:
        return transferencia.criado_em
    return solicitacao.criado_em


def _fim_atendimento(solicitacao):
    if solicitacao.status in {"APROVADA", "REJEITADA", "CONCLUIDA"}:
        return solicitacao.data_aprovacao
    return None


def _tempo_horas(solicitacao, unidade):
    inicio = _inicio_atendimento(solicitacao, unidade)
    fim = _fim_atendimento(solicitacao)
    if not inicio or not fim or fim < inicio:
        return None
    return round((fim - inicio).total_seconds() / 3600, 2)


@login_required
def analise_unidades(request):
    unidades = _unidades_permitidas(request).order_by("nome")
    unidade_id = request.GET.get("unidade")
    origem = request.GET.get("origem")
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")

    selecionada = unidades.filter(pk=unidade_id).first() if unidade_id else None
    base = Solicitacao.objects.select_related("unidade", "municipio", "bairro")
    base = base.filter(unidade__in=unidades)

    if selecionada:
        base = base.filter(unidade=selecionada)
    if origem in {"EXTERNA", "MANUAL", "TRANSFERIDA"}:
        base = base.filter(origem=origem)
    if inicio:
        base = base.filter(criado_em__date__gte=inicio)
    if fim:
        base = base.filter(criado_em__date__lte=fim)

    grupos = []
    unidades_relatorio = [selecionada] if selecionada else list(unidades)

    for unidade in unidades_relatorio:
        qs = base.filter(unidade=unidade)
        total = qs.count()
        pendentes = qs.filter(status__in=["PENDENTE", "EM_ANALISE", "CORRECAO"]).count()
        aprovadas = qs.filter(status__in=["APROVADA", "CONCLUIDA"]).count()
        rejeitadas = qs.filter(status="REJEITADA").count()

        tempos = []
        for solicitacao in qs.filter(status__in=["APROVADA", "REJEITADA", "CONCLUIDA"]):
            horas = _tempo_horas(solicitacao, unidade)
            if horas is not None:
                tempos.append(horas)

        media = round(sum(tempos) / len(tempos), 2) if tempos else None

        grupos.append({
            "unidade": unidade,
            "total": total,
            "pendentes": pendentes,
            "aprovadas": aprovadas,
            "rejeitadas": rejeitadas,
            "respondidas": len(tempos),
            "media_horas": media,
        })

    total_geral = sum(item["total"] for item in grupos)
    respondidas = sum(item["respondidas"] for item in grupos)
    medias = [item["media_horas"] for item in grupos if item["media_horas"] is not None]
    media_geral = round(sum(medias) / len(medias), 2) if medias else None

    return render(
        request,
        "analise/unidades.html",
        {
            "grupos": grupos,
            "unidades": unidades,
            "selecionada": selecionada,
            "origem": origem or "",
            "inicio": inicio or "",
            "fim": fim or "",
            "total_geral": total_geral,
            "respondidas": respondidas,
            "media_geral": media_geral,
        },
    )


@login_required
def painel_analise(request):
    return analise_unidades(request)


@login_required
def fila_analise(request):
    unidades = _unidades_permitidas(request)
    solicitacoes = Solicitacao.objects.filter(
        unidade__in=unidades,
        status__in=["PENDENTE", "EM_ANALISE", "CORRECAO"],
    ).select_related("municipio", "bairro", "unidade").order_by("criado_em")
    return render(request, "analise/fila.html", {"solicitacoes": solicitacoes})


@login_required
def detalhes(request, pk):
    solicitacao = get_object_or_404(Solicitacao, pk=pk)
    documentos = solicitacao.documentos.select_related("tipo_documento").all()
    historico = solicitacao.historico.select_related("usuario").order_by("-criado_em")
    return render(request, "analise/detalhes.html", {"solicitacao": solicitacao, "documentos": documentos, "historico": historico})


@login_required
def aprovar(request, pk):
    solicitacao = get_object_or_404(Solicitacao, pk=pk)
    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.aprovado_por = request.user.get_full_name() or request.user.username
    solicitacao.save(update_fields=["status", "data_aprovacao", "aprovado_por", "atualizado_em"])
    HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="APROVADA", detalhes="Solicitação aprovada.")
    messages.success(request, "Solicitação aprovada com sucesso.")
    return redirect("fila_analise")


@login_required
def solicitar_correcao(request, pk):
    solicitacao = get_object_or_404(Solicitacao, pk=pk)
    motivo = request.POST.get("motivo", "").strip()
    if request.method == "POST" and not motivo:
        messages.error(request, "Informe o motivo da correção.")
        return redirect("detalhes", pk=pk)
    if request.method == "POST":
        solicitacao.status = "CORRECAO"
        solicitacao.save(update_fields=["status", "atualizado_em"])
        HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="CORREÇÃO", detalhes=motivo)
        messages.success(request, "Correção solicitada.")
    return redirect("fila_analise")


@login_required
def indeferir(request, pk):
    solicitacao = get_object_or_404(Solicitacao, pk=pk)
    motivo = request.POST.get("motivo", "").strip()
    if request.method == "POST" and not motivo:
        messages.error(request, "Informe o motivo do indeferimento.")
        return redirect("detalhes", pk=pk)
    if request.method == "POST":
        solicitacao.status = "REJEITADA"
        solicitacao.data_aprovacao = timezone.now()
        solicitacao.save(update_fields=["status", "data_aprovacao", "atualizado_em"])
        HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="REJEITADA", detalhes=motivo)
        messages.success(request, "Solicitação rejeitada.")
    return redirect("fila_analise")


@login_required
def historico(request, pk):
    solicitacao = get_object_or_404(Solicitacao, pk=pk)
    historico = solicitacao.historico.select_related("usuario").order_by("-criado_em")
    return render(request, "analise/historico.html", {"solicitacao": solicitacao, "historico": historico})


@login_required
def estatisticas(request):
    unidades = _unidades_permitidas(request)
    dados = Solicitacao.objects.filter(unidade__in=unidades).values("status").annotate(total=Count("id")).order_by("status")
    return render(request, "analise/estatisticas.html", {"dados": dados, "total": sum(item["total"] for item in dados)})
