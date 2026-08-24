from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

from apps.solicitacoes.models import (
    Solicitacao,
    Municipio,
    Unidade,
    TipoEvento,
)
@login_required
def dashboard(request):

    hoje = timezone.localdate()

    proximos_30 = hoje + timedelta(days=30)

    context = {

        "eventos_hoje": Solicitacao.objects.filter(
            data_evento=hoje
        ).count(),

        "eventos_futuros": Solicitacao.objects.filter(
            data_evento__range=[hoje, proximos_30]
        ).count(),

        "pendentes": Solicitacao.objects.filter(
            status="EM_ANALISE"
        ).count(),

        "correcao": Solicitacao.objects.filter(
            status="CORRECAO"
        ).count(),

        "aprovadas": Solicitacao.objects.filter(
            status="APROVADA"
        ).count(),

        "indeferidas": Solicitacao.objects.filter(
            status="INDEFERIDA"
        ).count(),

    }

    return render(
        request,
        "dashboard/index.html",
        context
    )
@login_required
def eventos_hoje(request):

    hoje = timezone.localdate()

    eventos = Solicitacao.objects.filter(
        data_evento=hoje
    ).order_by("hora_inicio")

    return render(
        request,
        "dashboard/eventos_hoje.html",
        {
            "eventos": eventos
        }
    )
@login_required
def proximos_eventos_gestao(request):

    hoje = timezone.localdate()

    eventos = Solicitacao.objects.filter(
        data_evento__gte=hoje
    ).order_by("data_evento")

    return render(
        request,
        "dashboard/proximos.html",
        {
            "eventos": eventos
        }
    )
@login_required
def por_municipio(request):

    dados = (

        Solicitacao.objects

        .values("municipio__nome")

        .annotate(total=Count("id"))

        .order_by("-total")

    )

    return render(
        request,
        "dashboard/municipios.html",
        {
            "dados": dados
        }
    )
@login_required
def por_unidade(request):

    dados = (

        Solicitacao.objects

        .values("unidade__sigla")

        .annotate(total=Count("id"))

        .order_by("-total")

    )

    return render(
        request,
        "dashboard/unidades.html",
        {
            "dados": dados
        }
    )
@login_required
def por_tipo(request):

    dados = (

        Solicitacao.objects

        .values("tipo_evento__nome")

        .annotate(total=Count("id"))

        .order_by("-total")

    )

    return render(
        request,
        "dashboard/tipos.html",
        {
            "dados": dados
        }
    )
@login_required
def calendario(request):

    eventos = Solicitacao.objects.order_by(
        "data_evento"
    )

    return render(
        request,
        "dashboard/calendario.html",
        {
            "eventos": eventos
        }
    )
@login_required
def mapa(request):

    municipios = (

        Solicitacao.objects

        .values("municipio__nome")

        .annotate(total=Count("id"))

        .order_by("-total")

    )

    return render(
        request,
        "dashboard/mapa.html",
        {
            "municipios": municipios
        }
    )
@login_required
def listar_pendentes_opo(request):

    solicitacoes = Solicitacao.objects.filter(
        status="PENDENTE"
    ).order_by(
        "data_evento",
        "hora_inicio"
    )

    return render(
        request,
        "gestao/aprovacoes.html",
        {
            "solicitacoes": solicitacoes,
        }
    )