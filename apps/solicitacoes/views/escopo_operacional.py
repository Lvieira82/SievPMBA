"""Consultas operacionais da Gestão respeitando o escopo institucional."""

from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.solicitacoes.acesso_regras import escopo_usuario
from apps.solicitacoes.models import AnexoOPO, Solicitacao
from apps.solicitacoes.views.operacional import (
    detalhe_opo as _detalhe_opo,
    gerar_opo as _gerar_opo,
)


def _solicitacoes_no_escopo(user, queryset=None):
    qs = queryset if queryset is not None else Solicitacao.objects.all()
    acesso = escopo_usuario(user)

    if isinstance(acesso, dict):
        return qs
    if not acesso:
        return qs.none()

    if acesso.perfil == "CPR":
        return qs.filter(unidade__cpr_id=acesso.cpr_id)

    if acesso.perfil in {"UNIDADE", "OPERADOR"}:
        return qs.filter(unidade_id=acesso.unidade_id)

    if acesso.perfil == "COPPM":
        return qs

    return qs.none()


def _anexos_no_escopo(user):
    return AnexoOPO.objects.filter(
        solicitacao__in=_solicitacoes_no_escopo(user)
    ).select_related(
        "solicitacao",
        "solicitacao__unidade",
        "solicitacao__municipio",
        "solicitacao__bairro",
    )


@login_required
def opos_geradas(request):
    anexos = _anexos_no_escopo(request.user).order_by("-criado_em")
    agrupados = {}

    for anexo in anexos:
        codigo = anexo.solicitacao.protocolo
        agrupados.setdefault(codigo, {
            "codigo": codigo,
            "solicitacao": anexo.solicitacao,
            "arquivos": [],
        })
        agrupados[codigo]["arquivos"].append(anexo)

    return render(
        request,
        "gestao/opos_geradas.html",
        {"protocolos": list(agrupados.values())},
    )


@login_required
def detalhe_opo(request, id):
    solicitacao = get_object_or_404(
        _solicitacoes_no_escopo(request.user),
        pk=id,
    )
    return _detalhe_opo(request, solicitacao.id)


@login_required
def gerar_opo(request, id):
    get_object_or_404(_solicitacoes_no_escopo(request.user), pk=id)
    return _gerar_opo(request, id)


def _periodo_mapa(request):
    """Retorna o período informado no formulário, ou os próximos 30 dias."""
    hoje = timezone.localdate()
    inicio_raw = (request.GET.get("data_inicio") or "").strip()
    fim_raw = (request.GET.get("data_fim") or "").strip()

    try:
        inicio = datetime.strptime(inicio_raw, "%Y-%m-%d").date() if inicio_raw else hoje
    except ValueError:
        inicio = hoje
        inicio_raw = ""

    try:
        fim = datetime.strptime(fim_raw, "%Y-%m-%d").date() if fim_raw else inicio + timedelta(days=30)
    except ValueError:
        fim = inicio + timedelta(days=30)
        fim_raw = ""

    if fim < inicio:
        inicio, fim = fim, inicio

    return inicio, fim, inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")


@login_required
def mapa_eventos(request):
    inicio, fim, data_inicio, data_fim = _periodo_mapa(request)

    eventos = _solicitacoes_no_escopo(
        request.user,
        Solicitacao.objects.filter(
            data_evento__gte=inicio,
            data_evento__lte=fim,
        )
        .select_related("municipio", "bairro", "unidade")
        .order_by("data_evento", "hora_inicio"),
    )

    return render(
        request,
        "gestao/mapa_eventos.html",
        {
            "eventos": eventos,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        },
    )


@login_required
def gerar_mapa_eventos_pdf(request):
    inicio, fim, _, _ = _periodo_mapa(request)

    eventos = _solicitacoes_no_escopo(
        request.user,
        Solicitacao.objects.filter(
            data_evento__gte=inicio,
            data_evento__lte=fim,
            status="APROVADA",
        )
        .select_related("municipio", "bairro", "unidade")
        .order_by("data_evento", "hora_inicio"),
    )

    if not eventos.exists():
        return HttpResponse(
            "Nenhum evento aprovado encontrado no período e âmbito de gestão informados.",
            content_type="text/plain; charset=utf-8",
        )

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'inline; filename="mapa_eventos.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()

    rows = [["Data", "Hora", "Evento", "Município", "Unidade"]]
    for evento in eventos:
        rows.append([
            evento.data_evento.strftime("%d/%m/%Y"),
            evento.hora_inicio.strftime("%H:%M") if evento.hora_inicio else "-",
            evento.nome_evento,
            evento.municipio.nome if evento.municipio else "-",
            evento.unidade.sigla if evento.unidade else "-",
        ])

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#907C64")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))

    doc.build([
        Paragraph("MAPA DE EVENTOS - SiEv", styles["Title"]),
        Spacer(1, 12),
        table,
    ])
    return response
