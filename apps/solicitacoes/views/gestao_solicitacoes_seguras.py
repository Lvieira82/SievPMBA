import json
from datetime import date, timedelta

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
    hoje = timezone.localdate()
    inicio_padrao = hoje
    fim_padrao = hoje + timedelta(days=30)

    inicio_str = request.GET.get("inicio") or inicio_padrao.isoformat()
    fim_str = request.GET.get("fim") or fim_padrao.isoformat()
    try:
        inicio = date.fromisoformat(inicio_str)
        fim = date.fromisoformat(fim_str)
    except (ValueError, TypeError):
        inicio, fim = inicio_padrao, fim_padrao
        inicio_str, fim_str = inicio.isoformat(), fim.isoformat()

    if fim < inicio:
        inicio, fim = fim, inicio
        inicio_str, fim_str = inicio.isoformat(), fim.isoformat()

    eventos = list(
        Solicitacao.objects.filter(
            unidade__in=escopo_unidades(request.user),
            status__in=["APROVADA", "CORRECAO"],
            data_evento__range=[inicio, fim],
        )
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    cidades = {}
    dias = {}
    for evento in eventos:
        cidade = evento.municipio.nome if evento.municipio else "Sem cidade"
        cidades[cidade] = cidades.get(cidade, 0) + 1
        dia = evento.data_evento.strftime("%d/%m")
        dias[dia] = dias.get(dia, 0) + 1

    return render(request, "gestao/proximos_eventos.html", {
        "eventos": eventos,
        "filtro_inicio": inicio_str,
        "filtro_fim": fim_str,
        "total_eventos": len(eventos),
        "cidades_json": json.dumps(list(cidades.keys()), ensure_ascii=False),
        "cidades_valores_json": json.dumps(list(cidades.values())),
        "dias_json": json.dumps(list(dias.keys()), ensure_ascii=False),
        "dias_valores_json": json.dumps(list(dias.values())),
    })


@login_required
def listar_pendentes_opo_seguro(request):
    solicitacoes=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),status="PENDENTE").select_related("municipio","bairro","unidade").order_by("data_evento","hora_inicio")
    return render(request,"gestao/aprovacoes.html",{"solicitacoes":solicitacoes})
