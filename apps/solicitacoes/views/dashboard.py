from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.solicitacoes.acesso_regras import escopo_usuario
from apps.solicitacoes.models import Solicitacao


def _escopo_dashboard(user, queryset=None):
    qs = queryset if queryset is not None else Solicitacao.objects.all()
    acesso = escopo_usuario(user)

    if isinstance(acesso, dict):
        return qs
    if not acesso:
        return qs.none()

    if acesso.perfil == "COPPM":
        return qs
    if acesso.perfil == "CPR":
        return qs.filter(unidade__cpr_id=acesso.cpr_id)
    if acesso.perfil in {"UNIDADE", "OPERADOR"}:
        return qs.filter(unidade_id=acesso.unidade_id)

    return qs.none()


@login_required
def dashboard(request):
    hoje = timezone.localdate()
    limite = hoje + timedelta(days=30)
    base = _escopo_dashboard(request.user)

    eventos = (
        base.filter(data_evento__gte=hoje, data_evento__lt=limite)
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    context = {
        "eventos_hoje": base.filter(data_evento=hoje).count(),
        "eventos_futuros": eventos.count(),
        "pendentes": base.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "correcao": base.filter(status="CORRECAO").count(),
        "aprovadas": base.filter(status__in=["APROVADA", "CONCLUIDA"]).count(),
        "indeferidas": base.filter(status="REJEITADA").count(),
        "eventos": eventos,
    }
    return render(request, "dashboard/index.html", context)


@login_required
def eventos_hoje(request):
    eventos = _escopo_dashboard(
        request.user,
        Solicitacao.objects.filter(data_evento=timezone.localdate()),
    ).order_by("hora_inicio")
    return render(request, "dashboard/eventos_hoje.html", {"eventos": eventos})


@login_required
def proximos_eventos_gestao(request):
    hoje = timezone.localdate()
    limite = hoje + timedelta(days=30)
    eventos = (
        _escopo_dashboard(request.user)
        .filter(data_evento__gte=hoje, data_evento__lt=limite)
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )
    return render(request, "dashboard/proximos.html", {"eventos": eventos})


@login_required
def por_municipio(request):
    dados = (
        _escopo_dashboard(request.user)
        .values("municipio__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    return render(request, "dashboard/municipios.html", {"dados": dados})


@login_required
def por_unidade(request):
    dados = (
        _escopo_dashboard(request.user)
        .values("unidade__sigla")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    return render(request, "dashboard/unidades.html", {"dados": dados})


@login_required
def por_tipo(request):
    dados = (
        _escopo_dashboard(request.user)
        .values("tipo_evento__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    return render(request, "dashboard/tipos.html", {"dados": dados})


@login_required
def calendario(request):
    eventos = _escopo_dashboard(request.user).order_by("data_evento", "hora_inicio")
    return render(request, "dashboard/calendario.html", {"eventos": eventos})


@login_required
def mapa(request):
    municipios = (
        _escopo_dashboard(request.user)
        .values("municipio__nome")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    return render(request, "dashboard/mapa.html", {"municipios": municipios})


@login_required
def listar_pendentes_opo(request):
    solicitacoes = (
        _escopo_dashboard(request.user)
        .filter(status="PENDENTE")
        .select_related("municipio", "bairro", "unidade")
        .order_by("data_evento", "hora_inicio")
    )
    return render(request, "gestao/aprovacoes.html", {"solicitacoes": solicitacoes})
