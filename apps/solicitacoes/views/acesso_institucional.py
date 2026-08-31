from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.solicitacoes.models import Solicitacao


def _escopo_solicitacoes(request):
    if request.user.is_superuser or request.user.is_staff:
        return Solicitacao.objects.all()

    perfil = getattr(request.user, "perfil_siev", None)
    if not perfil or not perfil.ativo:
        return Solicitacao.objects.none()

    if perfil.perfil == "COPPM":
        return Solicitacao.objects.all()

    if perfil.perfil == "CPR" and perfil.cpr_id:
        return Solicitacao.objects.filter(unidade__cpr_id=perfil.cpr_id)

    if perfil.perfil == "UNIDADE" and perfil.unidade_id:
        return Solicitacao.objects.filter(unidade_id=perfil.unidade_id)

    return Solicitacao.objects.none()


def _exigir_perfil(request):
    if request.user.is_superuser or request.user.is_staff:
        return True
    perfil = getattr(request.user, "perfil_siev", None)
    if perfil and perfil.ativo and perfil.perfil in {"COPPM", "CPR", "UNIDADE"}:
        return True
    messages.error(request, "Usuário sem perfil institucional ativo.")
    return False


@login_required
def historico_gestao(request):
    if not _exigir_perfil(request):
        return redirect("login_gestao")

    hoje = timezone.localdate()
    escopo = _escopo_solicitacoes(request)
    eventos = (
        escopo
        .filter(data_evento__lt=hoje, status__in=["APROVADA", "CONCLUIDA", "REJEITADA"])
        .select_related("municipio", "unidade", "bairro")
        .order_by("-data_evento", "-hora_inicio")
    )

    dia = request.GET.get("dia")
    mes = request.GET.get("mes")
    ano = request.GET.get("ano")

    if dia:
        try:
            eventos = eventos.filter(data_evento=date.fromisoformat(dia))
        except ValueError:
            dia = ""
    if mes:
        try:
            eventos = eventos.filter(data_evento__month=int(mes))
        except (TypeError, ValueError):
            mes = ""
    if ano:
        try:
            eventos = eventos.filter(data_evento__year=int(ano))
        except (TypeError, ValueError):
            ano = ""

    anos = [
        item.year
        for item in (
            escopo
            .filter(data_evento__lt=hoje)
            .dates("data_evento", "year", order="DESC")
        )
    ]

    return render(
        request,
        "gestao/agenda.html",
        {
            "eventos": eventos,
            "anos": anos,
            "filtro_dia": dia,
            "filtro_mes": mes,
            "filtro_ano": ano,
            "titulo_historico": "Histórico de Eventos",
        },
    )


@login_required
def proximos_eventos_gestao_restrito(request):
    if not _exigir_perfil(request):
        return redirect("login_gestao")

    hoje = timezone.localdate()
    limite_semana = hoje + timedelta(days=7)

    eventos = (
        _escopo_solicitacoes(request)
        .filter(
            status__in=["APROVADA", "CORRECAO"],
            data_evento__gte=hoje,
            data_evento__lt=limite_semana,
        )
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    return render(request, "gestao/proximos_eventos.html", {"eventos": eventos})
