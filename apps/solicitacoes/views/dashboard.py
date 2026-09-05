from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import eh_desenvolvedor, eh_operador, escopo_unidades


def _solicitacoes_visiveis(user):
    if eh_desenvolvedor(user):
        return Solicitacao.objects.all()
    return Solicitacao.objects.filter(unidade__in=escopo_unidades(user))


@login_required
def dashboard(request):
    base = _solicitacoes_visiveis(request.user)
    hoje = timezone.localdate()

    if eh_operador(request.user):
        eventos = base.filter(data_evento=hoje, status="APROVADA").order_by("hora_inicio")
        return render(request, "dashboard/eventos_hoje.html", {"eventos": eventos})

    proximos_30 = hoje + timedelta(days=30)
    context = {
        "eventos_hoje": base.filter(data_evento=hoje).count(),
        "eventos_futuros": base.filter(data_evento__range=[hoje, proximos_30]).count(),
        "pendentes": base.filter(status__in=["PENDENTE", "EM_ANALISE"]).count(),
        "correcao": base.filter(status="CORRECAO").count(),
        "aprovadas": base.filter(status__in=["APROVADA", "CONCLUIDA"]).count(),
        "indeferidas": base.filter(status="REJEITADA").count(),
    }
    return render(request, "dashboard/index.html", context)


@login_required
def eventos_hoje(request):
    eventos = _solicitacoes_visiveis(request.user).filter(data_evento=timezone.localdate()).order_by("hora_inicio")
    return render(request, "dashboard/eventos_hoje.html", {"eventos": eventos})


@login_required
def proximos_eventos_gestao(request):
    eventos = _solicitacoes_visiveis(request.user).filter(data_evento__gte=timezone.localdate()).order_by("data_evento", "hora_inicio")
    return render(request, "dashboard/proximos.html", {"eventos": eventos})


@login_required
def por_municipio(request):
    dados = _solicitacoes_visiveis(request.user).values("municipio__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/municipios.html", {"dados": dados})


@login_required
def por_unidade(request):
    dados = _solicitacoes_visiveis(request.user).values("unidade__sigla").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/unidades.html", {"dados": dados})


@login_required
def por_tipo(request):
    dados = _solicitacoes_visiveis(request.user).values("tipo_evento__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/tipos.html", {"dados": dados})


@login_required
def calendario(request):
    eventos = _solicitacoes_visiveis(request.user).order_by("data_evento", "hora_inicio")
    return render(request, "dashboard/calendario.html", {"eventos": eventos})


@login_required
def mapa(request):
    municipios = _solicitacoes_visiveis(request.user).values("municipio__nome").annotate(total=Count("id")).order_by("-total")
    return render(request, "dashboard/mapa.html", {"municipios": municipios})


@login_required
def listar_pendentes_opo(request):
    solicitacoes = _solicitacoes_visiveis(request.user).filter(status="PENDENTE").select_related("municipio", "bairro", "unidade").order_by("data_evento", "hora_inicio")
    return render(request, "gestao/aprovacoes.html", {"solicitacoes": solicitacoes})
