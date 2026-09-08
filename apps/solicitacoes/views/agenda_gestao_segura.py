from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.solicitacoes.models import CPR, Municipio, Solicitacao
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

    data_inicio = (request.GET.get("data_inicio") or "").strip()
    data_fim = (request.GET.get("data_fim") or "").strip()
    cidade_id = (request.GET.get("cidade") or "").strip()
    cpr_id = (request.GET.get("cpr") or "").strip()
    unidade_id = (request.GET.get("unidade") or "").strip()

    if data_inicio:
        try:
            eventos = eventos.filter(data_evento__gte=date.fromisoformat(data_inicio))
        except ValueError:
            data_inicio = ""
    if data_fim:
        try:
            eventos = eventos.filter(data_evento__lte=date.fromisoformat(data_fim))
        except ValueError:
            data_fim = ""
    if cidade_id:
        try:
            eventos = eventos.filter(municipio_id=int(cidade_id))
        except (TypeError, ValueError):
            cidade_id = ""

    acesso = getattr(request.user, "acesso_institucional", None)
    perfil = getattr(acesso, "perfil", None)

    if perfil == "COPPM":
        if cpr_id:
            try:
                eventos = eventos.filter(unidade__cpr_id=int(cpr_id))
            except (TypeError, ValueError):
                cpr_id = ""
        if unidade_id:
            try:
                eventos = eventos.filter(unidade_id=int(unidade_id))
            except (TypeError, ValueError):
                unidade_id = ""
    elif perfil == "CPR":
        if unidade_id:
            try:
                eventos = eventos.filter(unidade_id=int(unidade_id))
            except (TypeError, ValueError):
                unidade_id = ""
    else:
        cpr_id = ""
        unidade_id = ""

    base_filtros = Solicitacao.objects.filter(
        unidade__in=unidades,
        status__in=["APROVADA", "CORRECAO"],
        data_evento__lt=hoje,
    )
    cidades = Municipio.objects.filter(
        pk__in=base_filtros.values_list("municipio_id", flat=True)
    ).order_by("nome")

    cprs = CPR.objects.none()
    if perfil == "COPPM":
        cprs = CPR.objects.filter(
            pk__in=unidades.values_list("cpr_id", flat=True),
            ativo=True,
        ).order_by("sigla")

    unidades_filtro = unidades.order_by("nome") if perfil in {"COPPM", "CPR"} else []

    return render(request, "gestao/agenda.html", {
        "eventos": eventos,
        "filtro_data_inicio": data_inicio,
        "filtro_data_fim": data_fim,
        "filtro_cidade": cidade_id,
        "filtro_cpr": cpr_id,
        "filtro_unidade": unidade_id,
        "cidades": cidades,
        "cprs": cprs,
        "unidades_filtro": unidades_filtro,
        "perfil_historico": perfil,
    })


@login_required
def proximos_eventos_gestao_seguro(request):
    if not pode_ver_proximos_eventos(request.user):
        return _negar(request, "Somente gestores de COPPM, CPR e Unidade podem consultar os próximos eventos.")

    hoje = timezone.localdate()
    limite = hoje + timedelta(days=14)
    eventos = (
        Solicitacao.objects
        .filter(
            unidade__in=escopo_unidades(request.user),
            status__in=["APROVADA", "CORRECAO"],
            data_evento__gte=hoje,
            data_evento__lte=limite,
        )
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    cidades = {}
    dias = {}
    for evento in eventos:
        cidade = evento.municipio.nome if evento.municipio else "Não informado"
        cidades[cidade] = cidades.get(cidade, 0) + 1
        dias[evento.data_evento] = dias.get(evento.data_evento, 0) + 1

    total = len(eventos)
    cores = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#65a30d"]
    cidades_grafico = []
    inicio = 0
    gradientes = []
    for indice, (nome, quantidade) in enumerate(sorted(cidades.items(), key=lambda x: (-x[1], x[0]))):
        percentual = quantidade * 100 / total if total else 0
        fim = inicio + percentual
        cor = cores[indice % len(cores)]
        cidades_grafico.append({
            "nome": nome,
            "quantidade": quantidade,
            "percentual": round(percentual, 1),
            "inicio": round(inicio, 2),
            "fim": round(fim, 2),
            "cor": cor,
        })
        gradientes.append(f"{cor} {inicio:.2f}% {fim:.2f}%")
        inicio = fim

    pizza_gradient = ", ".join(gradientes) if gradientes else "#e5e7eb 0% 100%"

    max_dia = max(dias.values(), default=0)
    dias_grafico = []
    cursor = hoje
    while cursor <= limite:
        quantidade = dias.get(cursor, 0)
        dias_grafico.append({
            "data": cursor,
            "nome": cursor.strftime("%d/%m"),
            "quantidade": quantidade,
            "percentual": round(quantidade * 100 / max_dia, 1) if max_dia else 0,
        })
        cursor += timedelta(days=1)

    return render(request, "gestao/proximos_eventos.html", {
        "eventos": eventos,
        "cidades_grafico": cidades_grafico,
        "dias_grafico": dias_grafico,
        "pizza_gradient": pizza_gradient,
        "total_eventos": total,
        "filtro_inicio": hoje.strftime("%Y-%m-%d"),
        "filtro_fim": limite.strftime("%Y-%m-%d"),
    })
