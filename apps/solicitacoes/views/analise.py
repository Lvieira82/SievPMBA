from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import (
    AnexoOPO,
    CumprimentoOPO,
    HistoricoSolicitacao,
    LogSistema,
    Solicitacao,
    TransferenciaSolicitacao,
)
from apps.solicitacoes.permissoes import (
    escopo_unidades,
    pode_ver_ranking,
    pode_ver_solicitacao,
)


def _unidades_permitidas(user):
    return escopo_unidades(user)


def _sem_acesso(request):
    messages.error(
        request,
        "A análise e o ranking estão disponíveis para gestores de COPPM, CPR e Unidade.",
    )
    return redirect("painel_gestao")


def _inicio_atendimento(solicitacao, unidade):
    transferencia = (
        TransferenciaSolicitacao.objects
        .filter(solicitacao=solicitacao, unidade_destino=unidade)
        .order_by("-criado_em")
        .first()
    )
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
