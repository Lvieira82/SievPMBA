"""Escopo institucional das consultas operacionais da Gestão."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.http import HttpResponse

from apps.solicitacoes.acesso_regras import escopo_usuario
from apps.solicitacoes.models import AnexoOPO, Solicitacao
from apps.solicitacoes.views.operacional import (
    detalhe_opo as _detalhe_opo,
    gerar_mapa_eventos_pdf as _gerar_mapa_eventos_pdf,
    gerar_opo as _gerar_opo,
    mapa_eventos as _mapa_eventos,
    opos_geradas as _opos_geradas,
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
    # COPPM tem visão de todo o território.
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
    return render(request, "gestao/opos_geradas.html", {"protocolos": list(agrupados.values())})


@login_required
def detalhe_opo(request, id):
    solicitacao = get_object_or_404(
        _solicitacoes_no_escopo(request.user),
        pk=id,
    )
    return _detalhe_opo(request, solicitacao.id)


@login_required
def gerar_opo(request, id):
    # A geração também precisa respeitar o território para impedir acesso direto por URL.
    get_object_or_404(_solicitacoes_no_escopo(request.user), pk=id)
    return _gerar_opo(request, id)


@login_required
def mapa_eventos(request):
    eventos = _solicitacoes_no_escopo(
        request.user,
        Solicitacao.objects.filter(data_evento__gte=timezone.localdate())
        .select_related("municipio", "bairro", "unidade")
        .order_by("data_evento", "hora_inicio"),
    )
    return render(request, "gestao/mapa_eventos.html", {"eventos": eventos})


@login_required
def gerar_mapa_eventos_pdf(request):
    eventos = _solicitacoes_no_escopo(
        request.user,
        Solicitacao.objects.filter(data_evento__gte=timezone.localdate())
        .select_related("municipio", "bairro", "unidade")
        .order_by("data_evento", "hora_inicio"),
    )

    # Reaproveita a mesma geração do sistema, mas restringe a consulta por um
    # escopo temporário através da própria lista de IDs permitidos.
    ids = list(eventos.values_list("id", flat=True))
    if not ids:
        return HttpResponse("Nenhum evento encontrado no seu âmbito de gestão.", content_type="text/plain")

    # A função original consulta o banco novamente; portanto, geramos aqui para
    # garantir que nenhum evento externo entre no PDF.
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
