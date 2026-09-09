from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.solicitacoes.middleware import MonitoramentoAcessosMiddleware
from apps.solicitacoes.models import LogSistema, Solicitacao
from apps.solicitacoes.permissoes import (
    eh_operador,
    escopo_unidades,
    pode_ver_mapa_eventos,
    pode_ver_proximos_eventos,
)


def _negar(request, mensagem="Você não possui permissão para acessar esta área."):
    messages.error(request, mensagem)
    return redirect("painel_gestao")


def _formatar_duracao(delta):
    if not delta:
        return "Sem dados"
    segundos = max(0, int(delta.total_seconds()))
    dias, resto = divmod(segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)
    partes = []
    if dias:
        partes.append(f"{dias}d")
    if horas:
        partes.append(f"{horas}h")
    if minutos or not partes:
        partes.append(f"{minutos}min")
    return " ".join(partes)


@login_required
def dashboard(request):
    # O Dashboard Operacional é exclusivo do Superusuário/Administrador.
    if not request.user.is_superuser:
        return _negar(request, "O Dashboard Operacional está disponível somente para o Superusuário Administrador.")

    unidades = escopo_unidades(request.user)
    base = Solicitacao.objects.filter(unidade__in=unidades)

    # Considera simultâneos os usuários com atividade real nos últimos 5 minutos.
    # A atividade é atualizada pela sessão, mas não gera um novo acesso histórico.
    acessos_simultaneos = len(MonitoramentoAcessosMiddleware.sessoes_ativas(minutos=5))

    # Visitantes não autenticados com atividade nos últimos 5 minutos.
    acessos_publico = MonitoramentoAcessosMiddleware.acessos_publicos_ativos(minutos=5)

    # Estatísticas históricas: um acesso = uma sessão, e não um refresh.
    logs_acesso = LogSistema.objects.filter(acao="ACESSO_SESSAO")
    tz = timezone.get_current_timezone()
    dia_mais_acessado = (
        logs_acesso
        .annotate(dia=TruncDate("criado_em", tzinfo=tz))
        .values("dia")
        .annotate(total=Count("id"))
        .order_by("-total", "dia")
        .first()
    )
    hora_mais_acessada = (
        logs_acesso
        .annotate(hora=TruncHour("criado_em", tzinfo=tz))
        .values("hora")
        .annotate(total=Count("id"))
        .order_by("-total", "hora")
        .first()
    )

    # Intervalo médio entre a chegada de uma solicitação e a seguinte.
    chegadas = list(
        Solicitacao.objects
        .order_by("criado_em")
        .values_list("criado_em", flat=True)
    )
    intervalos = [
        atual - anterior
        for anterior, atual in zip(chegadas, chegadas[1:])
        if anterior and atual and atual >= anterior
    ]
    intervalo_medio = sum(intervalos, timedelta()) / len(intervalos) if intervalos else None

    context = {
        "pendentes": base.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "correcao": base.filter(status="CORRECAO").count(),
        "aprovadas": base.filter(status__in=["APROVADA", "CONCLUIDA"]).count(),
        "indeferidas": base.filter(status="REJEITADA").count(),
        "acessos_simultaneos": acessos_simultaneos,
        "acessos_publico": acessos_publico,
        "dia_mais_acessado": dia_mais_acessado["dia"].strftime("%d/%m/%Y") if dia_mais_acessado else "Sem dados",
        "dia_mais_acessado_total": dia_mais_acessado["total"] if dia_mais_acessado else 0,
        "hora_mais_acessada": hora_mais_acessada["hora"].strftime("%H:%M") if hora_mais_acessada else "Sem dados",
        "hora_mais_acessada_total": hora_mais_acessada["total"] if hora_mais_acessada else 0,
        "media_tempo_solicitacoes": _formatar_duracao(intervalo_medio),
        "solicitacoes_com_tempo": len(intervalos) + 1 if intervalos else len(chegadas),
    }
    return render(request, "dashboard/index.html", context)


@login_required
def eventos_hoje(request):
    eventos = Solicitacao.objects.filter(
        unidade__in=escopo_unidades(request.user),
        data_evento=timezone.localdate(),
    ).order_by("hora_inicio")
    return render(request, "dashboard/eventos_hoje.html", {"eventos": eventos})


@login_required
def proximos_eventos_gestao(request):
    if not pode_ver_proximos_eventos(request.user):
        return _negar(request, "Somente gestores de COPPM, CPR e Unidade podem consultar os próximos eventos.")
    eventos = Solicitacao.objects.filter(
        unidade__in=escopo_unidades(request.user),
        data_evento__gte=timezone.localdate(),
    ).order_by("data_evento", "hora_inicio")
    return render(request, "dashboard/proximos.html", {"eventos": eventos})
