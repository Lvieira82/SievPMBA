from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.solicitacoes.models import Solicitacao
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

    eventos = (
        base.filter(data_evento__gte=hoje)
        .select_related("municipio", "bairro", "unidade", "tipo_evento")
        .order_by("data_evento", "hora_inicio")[:10]
    )

    context = {
        "eventos_hoje": base.filter(data_evento=hoje).count(),
        "eventos_futuros": base.filter(data_evento__range=[hoje, proximos_30]).count(),
        "pendentes": base.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "correcao": base.filter(status="CORRECAO").count(),
        "aprovadas": base.filter(status__in=["APROVADA", "CONCLUIDA"]).count(),
        "indeferidas": base.filter(status="REJEITADA").count(),
        "eventos": eventos,
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
