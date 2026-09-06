from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import (
    CumprimentoOPO,
    HistoricoSolicitacao,
    Solicitacao,
    TransferenciaSolicitacao,
    Unidade,
)
from apps.solicitacoes.permissoes import escopo_unidades, pode_ver_solicitacao, pode_ver_ranking


def _unidades_permitidas(request):
    return escopo_unidades(request.user)


def _sem_acesso(request):
    messages.error(request, "A análise e o ranking estão disponíveis para gestores de COPPM, CPR e Unidade.")
    return redirect("painel_gestao")


def _inicio_atendimento(solicitacao, unidade):
    transferencia = TransferenciaSolicitacao.objects.filter(solicitacao=solicitacao, unidade_destino=unidade).order_by("-criado_em").first()
    return transferencia.criado_em if transferencia else solicitacao.criado_em


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


def _resumo_cumprimento(solicitacao_ids):
    qs = CumprimentoOPO.objects.filter(opo__solicitacao_id__in=solicitacao_ids)
    sim = qs.filter(cumprida=True).count()
    nao = qs.filter(cumprida=False).count()
    total = sim + nao
    percentual = round(sim * 100 / total, 1) if total else None
    return {"sim": sim, "nao": nao, "total": total, "percentual": percentual}


def _grupos_unidades(base, unidades_relatorio):
    grupos = []
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
        cumprimento = _resumo_cumprimento(qs.values_list("id", flat=True))
        grupos.append({
            "unidade": unidade,
            "total": total,
            "pendentes": pendentes,
            "aprovadas": aprovadas,
            "rejeitadas": rejeitadas,
            "respondidas": len(tempos),
            "media_horas": media,
            **cumprimento,
        })
    return grupos


@login_required
def analise_unidades(request):
    if not pode_ver_ranking(request.user):
        return _sem_acesso(request)

    unidades = _unidades_permitidas(request).order_by("nome")
    unidade_id = request.GET.get("unidade")
    origem = request.GET.get("origem")
    inicio = request.GET.get("inicio")
    fim = request.GET.get("fim")

    selecionada = unidades.filter(pk=unidade_id).first() if unidade_id else None
    base = Solicitacao.objects.select_related("unidade", "municipio", "bairro").filter(unidade__in=unidades)
    if selecionada:
        base = base.filter(unidade=selecionada)
    if origem in {"EXTERNA", "MANUAL", "TRANSFERIDA"}:
        base = base.filter(origem=origem)
    if inicio:
        base = base.filter(data_evento__gte=inicio)
    if fim:
        base = base.filter(data_evento__lte=fim)

    unidades_relatorio = [selecionada] if selecionada else list(unidades)
    grupos = _grupos_unidades(base, unidades_relatorio)

    total_geral = sum(item["total"] for item in grupos)
    respondidas = sum(item["respondidas"] for item in grupos)
    medias = [item["media_horas"] for item in grupos if item["media_horas"] is not None]
    media_geral = round(sum(medias) / len(medias), 2) if medias else None

    cumprimento_geral = _resumo_cumprimento(base.values_list("id", flat=True))

    ranking_cpr = []
    if getattr(request.user, "acesso_institucional", None) and request.user.acesso_institucional.perfil == "COPPM" and not selecionada:
        por_cpr = {}
        for unidade in unidades_relatorio:
            item = next((x for x in grupos if x["unidade"].id == unidade.id), None)
            if not item:
                continue
            cpr = unidade.cpr
            chave = cpr.id
            if chave not in por_cpr:
                por_cpr[chave] = {"cpr": cpr, "total": 0, "sim": 0, "nao": 0}
            por_cpr[chave]["total"] += item["total"]
            por_cpr[chave]["sim"] += item["sim"]
            por_cpr[chave]["nao"] += item["nao"]
        for item in por_cpr.values():
            respondidos = item["sim"] + item["nao"]
            item["percentual"] = round(item["sim"] * 100 / respondidos, 1) if respondidos else None
            item["respondidos"] = respondidos
        ranking_cpr = sorted(por_cpr.values(), key=lambda x: (x["percentual"] is not None, x["percentual"] or -1), reverse=True)

    return render(request, "analise/unidades.html", {
        "grupos": grupos,
        "unidades": unidades,
        "selecionada": selecionada,
        "origem": origem or "",
        "inicio": inicio or "",
        "fim": fim or "",
        "total_geral": total_geral,
        "respondidas": respondidas,
        "media_geral": media_geral,
        "cumprimento_geral": cumprimento_geral,
        "ranking_cpr": ranking_cpr,
        "eh_coppm": bool(getattr(getattr(request.user, "acesso_institucional", None), "perfil", None) == "COPPM"),
    })


@login_required
def painel_analise(request):
    return analise_unidades(request)


@login_required
def fila_analise(request):
    if not pode_ver_ranking(request.user):
        return _sem_acesso(request)
    unidades = _unidades_permitidas(request)
    solicitacoes = Solicitacao.objects.filter(unidade__in=unidades, status__in=["PENDENTE", "EM_ANALISE", "CORRECAO"]).select_related("municipio", "bairro", "unidade").order_by("criado_em")
    return render(request, "analise/fila.html", {"solicitacoes": solicitacoes})


@login_required
def detalhes(request, pk):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=pk)
    if not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("analise_unidades")
    documentos = solicitacao.documentos.select_related("tipo_documento").all()
    historico = solicitacao.historico.select_related("usuario").order_by("-criado_em")
    return render(request, "analise/detalhes.html", {"solicitacao": solicitacao, "documentos": documentos, "historico": historico})


@login_required
def aprovar(request, pk):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=pk)
    if not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("fila_analise")
    if not solicitacao.documentos.exists():
        messages.error(request, "A solicitação não pode ser aprovada sem documentos anexados.")
        return redirect("detalhes", pk=pk)
    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.aprovado_por = request.user.get_full_name() or request.user.username
    solicitacao.save(update_fields=["status", "data_aprovacao", "aprovado_por", "atualizado_em"])
    HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="APROVADA", observacao="Solicitação aprovada.")
    messages.success(request, "Solicitação aprovada com sucesso.")
    return redirect("fila_analise")


@login_required
def solicitar_correcao(request, pk):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=pk)
    if not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("fila_analise")
    motivo = request.POST.get("motivo", "").strip()
    if request.method == "POST" and not solicitacao.documentos.exists():
        messages.error(request, "A solicitação não pode ser enviada para correção sem documentos anexados.")
        return redirect("detalhes", pk=pk)
    if request.method == "POST" and not motivo:
        messages.error(request, "Informe o motivo da correção.")
        return redirect("detalhes", pk=pk)
    if request.method == "POST":
        solicitacao.status = "CORRECAO"
        solicitacao.save(update_fields=["status", "atualizado_em"])
        HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="CORREÇÃO", observacao=motivo)
        messages.success(request, "Correção solicitada.")
    return redirect("fila_analise")


@login_required
def indeferir(request, pk):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=pk)
    if not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("analise_unidades")
    motivo = request.POST.get("motivo", "").strip()
    if request.method == "POST" and not motivo:
        messages.error(request, "Informe o motivo do indeferimento.")
        return redirect("detalhes", pk=pk)
    if request.method == "POST":
        solicitacao.status = "REJEITADA"
        solicitacao.data_aprovacao = timezone.now()
        solicitacao.save(update_fields=["status", "data_aprovacao", "atualizado_em"])
        HistoricoSolicitacao.objects.create(solicitacao=solicitacao, usuario=request.user, acao="REJEITADA", observacao=motivo)
        messages.success(request, "Solicitação rejeitada.")
    return redirect("fila_analise")


@login_required
def historico(request, pk):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=pk)
    if not pode_ver_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui acesso a esta solicitação.")
        return redirect("analise_unidades")
    historico = solicitacao.historico.select_related("usuario").order_by("-criado_em")
    return render(request, "analise/historico.html", {"solicitacao": solicitacao, "historico": historico})


@login_required
def estatisticas(request):
    if not pode_ver_ranking(request.user):
        return _sem_acesso(request)
    unidades = _unidades_permitidas(request)
    dados = Solicitacao.objects.filter(unidade__in=unidades).values("status").annotate(total=Count("id")).order_by("status")
    return render(request, "analise/estatisticas.html", {"dados": dados, "total": sum(item["total"] for item in dados)})
