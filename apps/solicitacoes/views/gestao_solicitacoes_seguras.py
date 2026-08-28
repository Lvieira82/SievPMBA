from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from apps.solicitacoes.models import Solicitacao
from apps.solicitacoes.permissoes import escopo_unidades

@login_required
def agenda_gestao_segura(request):
    qs=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),status__in=["APROVADA","CORRECAO"],data_evento__lt=timezone.localdate()).select_related("municipio","unidade","bairro").order_by("-data_evento","-hora_inicio")
    dia=request.GET.get("dia"); mes=request.GET.get("mes"); ano=request.GET.get("ano")
    try:
        if dia: qs=qs.filter(data_evento=date.fromisoformat(dia))
        if mes: qs=qs.filter(data_evento__month=int(mes))
        if ano: qs=qs.filter(data_evento__year=int(ano))
    except (ValueError,TypeError): pass
    return render(request,"gestao/agenda.html",{"eventos":qs,"anos":sorted(set(qs.values_list("data_evento__year",flat=True)),reverse=True),"filtro_dia":dia or "","filtro_mes":mes or "","filtro_ano":ano or ""})

@login_required
def proximos_eventos_gestao_seguro(request):
    eventos=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),status__in=["APROVADA","CORRECAO"],data_evento__gte=timezone.localdate()).select_related("municipio","unidade","bairro").order_by("data_evento","hora_inicio")
    return render(request,"gestao/proximos_eventos.html",{"eventos":eventos})

@login_required
def listar_pendentes_opo_seguro(request):
    solicitacoes=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),status="PENDENTE").select_related("municipio","bairro","unidade").order_by("data_evento","hora_inicio")
    return render(request,"gestao/aprovacoes.html",{"solicitacoes":solicitacoes})
