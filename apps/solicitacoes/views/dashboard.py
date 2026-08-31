from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.solicitacoes.models import Solicitacao


@login_required
def dashboard(request):
    hoje = timezone.localdate()
    limite_semana = hoje + timedelta(days=7)
    eventos = (
        Solicitacao.objects
        .filter(data_evento__gte=hoje, data_evento__lt=limite_semana)
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    context = {
        "eventos_hoje": Solicitacao.objects.filter(data_evento=hoje).count(),
        "eventos_futuros": eventos.count(),
        "pendentes": Solicitacao.objects.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "correcao": Solicitacao.objects.filter(status="CORRECAO").count(),
        "aprovadas": Solicitacao.objects.filter(status__in=["APROVADA", "CONCLUIDA"]).count(),
        "indeferidas": Solicitacao.objects.filter(status="REJEITADA").count(),
        "eventos": eventos,
    }
    return render(request, "dashboard/index.html", context)


@login_required
def eventos_hoje(request):
    eventos = Solicitacao.objects.filter(data_evento=timezone.localdate()).order_by("hora_inicio")
    return render(request, "dashboard/eventos_hoje.html", {"eventos": eventos})


@login_required
def proximos_eventos_gestao(request):
    hoje = timezone.localdate()
    limite_semana = hoje + timedelta(days=7)
    eventos = (
        Solicitacao.objects
        .filter(data_evento__gte=hoje, data_evento__lt=limite_semana)
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )
    return render(request, "dashboard/proximos.html", {"eventos": eventos})


@login_required
def por_municipio(request):
    dados = Solicitacao.objects.values("municipio__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/municipios.html", {"dados": dados})


@login_required
def por_unidade(request):
    dados = Solicitacao.objects.values("unidade__sigla").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/unidades.html", {"dados": dados})


@login_required
def por_tipo(request):
    dados = Solicitacao.objects.values("tipo_evento__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/tipos.html", {"dados": dados})


@login_required
def calendario(request):
    eventos = Solicitacao.objects.order_by("data_evento", "hora_inicio")
    return render(request, "dashboard/calendario.html", {"eventos": eventos})


@login_required
def mapa(request):
    municipios = Solicitacao.objects.values("municipio__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/mapa.html", {"municipios": municipios})


@login_required
def listar_pendentes_opo(request):
    solicitacoes = Solicitacao.objects.filter(status="PENDENTE").select_related("municipio", "bairro", "unidade").order_by("data_evento", "hora_inicio")
    return render(request, "gestao/aprovacoes.html", {"solicitacoes": solicitacoes})
