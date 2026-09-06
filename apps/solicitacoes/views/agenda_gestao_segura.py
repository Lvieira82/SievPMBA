from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import pode_ver_historico, pode_ver_proximos_eventos, escopo_unidades


def _negar(request, mensagem):
    messages.error(request, mensagem)
    return redirect("painel_gestao")


@login_required
def agenda_gestao_segura(request):
    if not pode_ver_historico(request.user):
        return _negar(request, "Somente gestores de COPPM, CPR e Unidade podem consultar os históricos.")

    hoje = timezone.localdate()
    unidades = escopo_unidades(request.user)
    eventos = (
        Solicitacao.objects
        .filter(
            unidade__in=unidades,
            status__in=["APROVADA", "CORRECAO"],
            data_evento__lt=hoje,
        )
        .select_related("municipio", "unidade", "bairro")
        .order_by("-data_evento", "-hora_inicio")
    )

    dia = request.GET.get("dia")
    if dia:
        try:
            eventos = eventos.filter(data_evento=date.fromisoformat(dia))
        except ValueError:
            dia = ""

    mes = request.GET.get("mes")
    if mes:
        try:
            eventos = eventos.filter(data_evento__month=int(mes))
        except (TypeError, ValueError):
            mes = ""

    ano = request.GET.get("ano")
    if ano:
        try:
            eventos = eventos.filter(data_evento__year=int(ano))
        except (TypeError, ValueError):
            ano = ""

    anos = [
        item.year
        for item in (
            Solicitacao.objects
            .filter(
                unidade__in=unidades,
                status__in=["APROVADA", "CORRECAO"],
                data_evento__lt=hoje,
            )
            .dates("data_evento", "year", order="DESC")
        )
    ]
    return render(request, "gestao/agenda.html", {
        "eventos": eventos,
        "anos": anos,
        "filtro_dia": dia,
        "filtro_mes": mes,
        "filtro_ano": ano,
    })


@login_required
def proximos_eventos_gestao_seguro(request):
    if not pode_ver_proximos_eventos(request.user):
        return _negar(request, "Somente gestores de COPPM, CPR e Unidade podem consultar os próximos eventos.")

    eventos = (
        Solicitacao.objects
        .filter(
            unidade__in=escopo_unidades(request.user),
            status__in=["APROVADA", "CORRECAO"],
            data_evento__gte=timezone.localdate(),
        )
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )
    return render(request, "gestao/proximos_eventos.html", {"eventos": eventos})
