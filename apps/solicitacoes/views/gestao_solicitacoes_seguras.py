from collections import OrderedDict
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
    limite_futuro = hoje + timedelta(days=15)
    fim_padrao = limite_futuro

    inicio_str = request.GET.get("inicio") or inicio_padrao.isoformat()
    fim_str = request.GET.get("fim") or fim_padrao.isoformat()
    try:
        inicio = date.fromisoformat(inicio_str)
        fim = date.fromisoformat(fim_str)
    except (ValueError, TypeError):
        inicio, fim = inicio_padrao, fim_padrao

    if fim < inicio:
        inicio, fim = fim, inicio

    if inicio < hoje:
        inicio = hoje
    if fim > limite_futuro:
        fim = limite_futuro
    if fim < inicio:
        fim = inicio

    inicio_str = inicio.isoformat()
    fim_str = fim.isoformat()

    # A unidade gravada na Solicitacao representa sempre a unidade atualmente
    # responsavel. Em uma transferencia, esse campo e atualizado para a unidade
    # de destino; portanto, Eventos Futuros nunca deve usar a unidade de origem
    # para classificar ou exibir o evento.
    eventos = list(
        Solicitacao.objects.filter(
            unidade__in=escopo_unidades(request.user),
            status__in=["APROVADA", "CORRECAO"],
            data_evento__range=[inicio, fim],
        )
        .select_related("municipio", "unidade", "unidade__cpr", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    cidades = {}
    dias = {}
    for evento in eventos:
        cidade = evento.municipio.nome if evento.municipio else "Sem cidade"
        cidades[cidade] = cidades.get(cidade, 0) + 1
        dia = evento.data_evento.strftime("%d/%m")
        dias[dia] = dias.get(dia, 0) + 1

    total_cidades = sum(cidades.values()) or 1
    cores = ["#3b9ddd", "#f45b7a", "#ff9f43", "#8e7dff", "#2fcf9d", "#e56b6f", "#4d96ff", "#f7c948"]
    cidades_grafico = []
    acumulado = 0
    for indice, (nome, quantidade) in enumerate(cidades.items()):
        percentual = (quantidade / total_cidades) * 100
        cidades_grafico.append({
            "nome": nome,
            "quantidade": quantidade,
            "percentual": percentual,
            "inicio": acumulado,
            "cor": cores[indice % len(cores)],
        })
        acumulado += percentual

    maior_dia = max(dias.values()) if dias else 1

    def cor_por_quantidade(quantidade):
        if quantidade == 0:
            return "#e5e7eb"
        if quantidade <= 2:
            return "#FFD600"
        if quantidade <= 4:
            return "#FF9800"
        if quantidade <= 6:
            return "#F44336"
        return "#FF1744"

    dias_grafico = []
    dia_atual = inicio
    while dia_atual <= fim:
        quantidade = dias.get(dia_atual.strftime("%d/%m"), 0)
        percentual = (quantidade / maior_dia) * 100 if maior_dia else 0
        dias_grafico.append({
            "nome": dia_atual.strftime("%d/%m"),
            "quantidade": quantidade,
            "percentual": percentual,
            "cor": cor_por_quantidade(quantidade),
        })
        dia_atual += timedelta(days=1)

    acesso = getattr(request.user, "acesso_institucional", None)
    perfil_proximos = getattr(acesso, "perfil", None)
    if request.user.is_superuser or request.user.is_staff:
        perfil_proximos = "COPPM"

    # A arvore apresentada para a COPPM e construida a partir da unidade atual
    # de cada solicitacao. Assim, uma solicitacao transferida deixa de aparecer
    # no CPR/unidade de origem e passa a aparecer somente no destino final.
    cprs_pastas_map = OrderedDict()
    for evento in eventos:
        unidade = evento.unidade
        if not unidade or not unidade.cpr:
            continue
        cpr = unidade.cpr
        cpr_key = cpr.pk
        if cpr_key not in cprs_pastas_map:
            cprs_pastas_map[cpr_key] = {
                "nome": cpr.sigla,
                "quantidade": 0,
                "unidades_map": OrderedDict(),
            }
        pasta = cprs_pastas_map[cpr_key]
        pasta["quantidade"] += 1
        unidade_key = unidade.pk
        if unidade_key not in pasta["unidades_map"]:
            pasta["unidades_map"][unidade_key] = {
                "nome": unidade.sigla,
                "quantidade": 0,
            }
        pasta["unidades_map"][unidade_key]["quantidade"] += 1

    cprs_pastas = []
    for pasta in cprs_pastas_map.values():
        pasta["unidades"] = list(pasta.pop("unidades_map").values())
        cprs_pastas.append(pasta)

    rotulo_agrupamento = "CPR" if perfil_proximos == "COPPM" else "cidade"

    return render(request, "gestao/proximos_eventos.html", {
        "eventos": eventos,
        "filtro_inicio": inicio_str,
        "filtro_fim": fim_str,
        "total_eventos": len(eventos),
        "cidades_grafico": cidades_grafico,
        "dias_grafico": dias_grafico,
        "perfil_proximos": perfil_proximos,
        "cprs_pastas": cprs_pastas,
        "rotulo_agrupamento": rotulo_agrupamento,
    })


@login_required
def listar_pendentes_opo_seguro(request):
    solicitacoes=Solicitacao.objects.filter(unidade__in=escopo_unidades(request.user),status="PENDENTE").select_related("municipio","bairro","unidade").order_by("data_evento","hora_inicio")
    return render(request,"gestao/aprovacoes.html",{"solicitacoes":solicitacoes})
