from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.solicitacoes.middleware import MonitoramentoAcessosMiddleware
from apps.solicitacoes.models import LogSistema, Solicitacao
from apps.solicitacoes.permissoes import eh_operador, escopo_unidades, pode_ver_proximos_eventos


def _negar(request, mensagem="Você não possui permissão para acessar esta área."):
    messages.error(request, mensagem)
    return redirect("painel_gestao")


def _formatar_duracao(delta):
    """Formata duração com precisão de minutos e segundos, sem arredondar."""
    if delta is None:
        return "Sem dados"
    segundos_total = max(0, int(delta.total_seconds()))
    horas, resto = divmod(segundos_total, 3600)
    minutos, segundos = divmod(resto, 60)

    if horas:
        return f"{horas}h {minutos:02d}min {segundos:02d}s"
    if minutos:
        return f"{minutos}min {segundos:02d}s"
    return f"{segundos}s"


def _tempo_aceite_envio(request):
    if not request.user.is_superuser:
        return _negar(request, "Esta visualização está disponível somente para o Administrador.")
    logs = LogSistema.objects.filter(acao="TEMPO_ACEITE_TERMO_ATE_ENVIO").select_related("solicitacao")
    valores = []
    for log in logs:
        try:
            segundos = float((log.detalhes or "").split("segundos=", 1)[1].split()[0])
        except (IndexError, ValueError):
            continue
        if 0 <= segundos <= 24 * 60 * 60:
            valores.append((log, segundos))
    total = len(valores)
    media = sum(v for _, v in valores) / total if total else 0
    minimo = min((v for _, v in valores), default=0)
    maximo = max((v for _, v in valores), default=0)
    ordenados = sorted(v for _, v in valores)
    if ordenados:
        meio = total // 2
        mediana = ordenados[meio] if total % 2 else (ordenados[meio - 1] + ordenados[meio]) / 2
    else:
        mediana = 0

    hoje = timezone.localdate()
    ultimos = [(log, segundos) for log, segundos in valores if timezone.localtime(log.criado_em).date() == hoje]
    media_hoje = sum(v for _, v in ultimos) / len(ultimos) if ultimos else 0
    registros = []
    for log, segundos in sorted(valores, key=lambda item: item[0].criado_em, reverse=True)[:100]:
        registros.append({
            "data": timezone.localtime(log.criado_em),
            "protocolo": log.solicitacao.protocolo if log.solicitacao else "-",
            "solicitante": log.solicitacao.solicitante if log.solicitacao else "-",
            "segundos": segundos,
            "duracao_formatada": _formatar_duracao(timedelta(seconds=segundos)),
        })

    return render(request, "dashboard/tempo_solicitacao.html", {
        "total": total, "media": media, "media_formatada": _formatar_duracao(timedelta(seconds=media)),
        "mediana_formatada": _formatar_duracao(timedelta(seconds=mediana)),
        "minimo_formatado": _formatar_duracao(timedelta(seconds=minimo)),
        "maximo_formatado": _formatar_duracao(timedelta(seconds=maximo)),
        "media_hoje_formatada": _formatar_duracao(timedelta(seconds=media_hoje)),
        "total_hoje": len(ultimos), "registros": registros,
    })


@login_required
def dashboard(request):
    if request.user.is_superuser and request.GET.get("aba") == "tempo":
        return _tempo_aceite_envio(request)
    if not request.user.is_superuser:
        return _negar(request, "O Dashboard Operacional está disponível somente para o Superusuário Administrador.")
    unidades = escopo_unidades(request.user)
    base = Solicitacao.objects.filter(unidade__in=unidades)
    acessos_simultaneos = len(MonitoramentoAcessosMiddleware.sessoes_ativas(minutos=5))
    acessos_publico = MonitoramentoAcessosMiddleware.acessos_publicos_ativos(minutos=5)
    logs_acesso = LogSistema.objects.filter(acao="ACESSO_SESSAO")
    tz = timezone.get_current_timezone()
    dia_mais_acessado = logs_acesso.annotate(dia=TruncDate("criado_em", tzinfo=tz)).values("dia").annotate(total=Count("id")).order_by("-total", "dia").first()
    hora_mais_acessada = logs_acesso.annotate(hora=TruncHour("criado_em", tzinfo=tz)).values("hora").annotate(total=Count("id")).order_by("-total", "hora").first()
    chegadas = list(Solicitacao.objects.order_by("criado_em").values_list("criado_em", flat=True))
    intervalos = [atual - anterior for anterior, atual in zip(chegadas, chegadas[1:]) if anterior and atual and atual >= anterior]
    intervalo_medio = sum(intervalos, timedelta()) / len(intervalos) if intervalos else None
    context = {
        "pendentes": base.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(), "correcao": base.filter(status="CORRECAO").count(),
        "aprovadas": base.filter(status__in=["APROVADA", "CONCLUIDA"]).count(), "indeferidas": base.filter(status="REJEITADA").count(),
        "acessos_simultaneos": acessos_simultaneos, "acessos_publico": acessos_publico,
        "dia_mais_acessado": dia_mais_acessado["dia"].strftime("%d/%m/%Y") if dia_mais_acessado else "Sem dados", "dia_mais_acessado_total": dia_mais_acessado["total"] if dia_mais_acessado else 0,
        "hora_mais_acessada": hora_mais_acessada["hora"].strftime("%H:%M") if hora_mais_acessada else "Sem dados", "hora_mais_acessada_total": hora_mais_acessada["total"] if hora_mais_acessada else 0,
        "media_tempo_solicitacoes": _formatar_duracao(intervalo_medio), "solicitacoes_com_tempo": len(intervalos) + 1 if intervalos else len(chegadas),
    }
    return render(request, "dashboard/index.html", context)


@login_required
def eventos_hoje(request):
    eventos = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user), data_evento=timezone.localdate()).order_by("hora_inicio")
    return render(request, "dashboard/eventos_hoje.html", {"eventos": eventos})


@login_required
def proximos_eventos_gestao(request):
    if not pode_ver_proximos_eventos(request.user): return _negar(request, "Somente gestores de COPPM, CPR e Unidade podem consultar os próximos eventos.")
    eventos = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user), data_evento__gte=timezone.localdate()).order_by("data_evento", "hora_inicio")
    return render(request, "dashboard/proximos.html", {"eventos": eventos})
