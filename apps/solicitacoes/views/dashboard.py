from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.solicitacoes.models import LogSistema, Solicitacao
from apps.solicitacoes.permissoes import (
    eh_operador,
    escopo_unidades,
    pode_ver_dashboard,
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
    if not pode_ver_dashboard(request.user):
        return _negar(request, "O Dashboard está disponível somente para o Gestor de Unidade e o Desenvolvedor.")
    if eh_operador(request.user):
        return _negar(request)

    unidades = escopo_unidades(request.user)
    base = Solicitacao.objects.filter(unidade__in=unidades)
    hoje = timezone.localdate()
    proximos_30 = hoje + timedelta(days=30)
    agora = timezone.now()

    # Considera simultâneos os usuários/clientes que fizeram uma requisição
    # nos últimos 5 minutos. Isso mede atividade real, e não apenas sessão aberta.
    janela_simultanea = agora - timedelta(minutes=5)
    acessos_recentes = LogSistema.objects.filter(
        acao="ACESSO_SISTEMA",
        criado_em__gte=janela_simultanea,
    ).values("usuario_id", "ip")
    identidades_ativas = set()
    for acesso in acessos_recentes:
        if acesso["usuario_id"]:
            identidades_ativas.add(("usuario", acesso["usuario_id"]))
        elif acesso["ip"]:
            identidades_ativas.add(("ip", acesso["ip"]))
    acessos_simultaneos = len(identidades_ativas)

    # Estatísticas históricas de acesso registradas pelo middleware.
    logs_acesso = LogSistema.objects.filter(acao="ACESSO_SISTEMA")
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

    # Tempo médio de processamento: criação da solicitação até a aprovação.
    tempos = base.filter(data_aprovacao__isnull=False).values_list("criado_em", "data_aprovacao")
    duracoes = [fim - inicio for inicio, fim in tempos if inicio and fim and fim >= inicio]
    media_tempo = sum(duracoes, timedelta()) / len(duracoes) if duracoes else None

    context = {
        "eventos_hoje": base.filter(data_evento=hoje).count(),
        "eventos_futuros": base.filter(data_evento__range=[hoje, proximos_30]).count(),
        "pendentes": base.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "correcao": base.filter(status="CORRECAO").count(),
        "aprovadas": base.filter(status__in=["APROVADA", "CONCLUIDA"]).count(),
        "indeferidas": base.filter(status="REJEITADA").count(),
        "acessos_simultaneos": acessos_simultaneos,
        "dia_mais_acessado": dia_mais_acessado["dia"].strftime("%d/%m/%Y") if dia_mais_acessado else "Sem dados",
        "dia_mais_acessado_total": dia_mais_acessado["total"] if dia_mais_acessado else 0,
        "hora_mais_acessada": hora_mais_acessada["hora"].strftime("%H:%M") if hora_mais_acessada else "Sem dados",
        "hora_mais_acessada_total": hora_mais_acessada["total"] if hora_mais_acessada else 0,
        "media_tempo_solicitacoes": _formatar_duracao(media_tempo),
        "solicitacoes_com_tempo": len(duracoes),
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


@login_required
def por_municipio(request):
    if not pode_ver_dashboard(request.user):
        return _negar(request)
    dados = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user)).values("municipio__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/municipios.html", {"dados": dados})


@login_required
def por_unidade(request):
    if not pode_ver_dashboard(request.user):
        return _negar(request)
    dados = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user)).values("unidade__sigla").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/unidades.html", {"dados": dados})


@login_required
def por_tipo(request):
    if not pode_ver_dashboard(request.user):
        return _negar(request)
    dados = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user)).values("tipo_evento__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/tipos.html", {"dados": dados})


@login_required
def calendario(request):
    if not pode_ver_dashboard(request.user):
        return _negar(request)
    eventos = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user)).order_by("data_evento", "hora_inicio")
    return render(request, "dashboard/calendario.html", {"eventos": eventos})


@login_required
def mapa(request):
    if not pode_ver_mapa_eventos(request.user):
        return _negar(request, "O mapa de eventos está disponível para gestores de CPR e Unidade.")
    municipios = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user)).values("municipio__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/mapa.html", {"municipios": municipios})


@login_required
def listar_pendentes_opo(request):
    solicitacoes = Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user), status="PENDENTE").select_related("municipio", "bairro", "unidade").order_by("data_evento", "hora_inicio")
    return render(request, "gestao/aprovacoes.html", {"solicitacoes": solicitacoes})
