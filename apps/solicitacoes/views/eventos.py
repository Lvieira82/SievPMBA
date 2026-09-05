from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from ..models import Solicitacao
from ..models_acesso import AcessoInstitucional


def _acesso_por_matricula(matricula):
    return (
        AcessoInstitucional.objects
        .select_related("usuario", "cpr", "unidade")
        .filter(matricula__iexact=matricula, ativo=True, usuario__is_active=True)
        .first()
    )


def _eventos_do_acesso(acesso, hoje):
    eventos = (
        Solicitacao.objects
        .filter(data_evento=hoje, status="APROVADA")
        .select_related("municipio", "unidade", "bairro")
        .order_by("hora_inicio", "nome_evento")
    )
    if acesso.perfil == "OPERADOR":
        if not acesso.unidade_id:
            return eventos.none()
        return eventos.filter(unidade_id=acesso.unidade_id)
    if acesso.perfil == "UNIDADE":
        return eventos.filter(unidade_id=acesso.unidade_id)
    if acesso.perfil == "CPR":
        return eventos.filter(unidade__cpr_id=acesso.cpr_id)
    if acesso.perfil == "COPPM":
        return eventos
    return eventos.none()


@login_required
def eventos_dia(request):
    acesso_logado = getattr(request.user, "acesso_institucional", None)
    if not acesso_logado or not acesso_logado.ativo or not request.user.is_active:
        messages.error(request, "Acesso institucional não autorizado.")
        return redirect("login_gestao")

    if request.method == "GET":
        return render(request, "solicitacoes/eventos_dia.html", {"acesso_logado": acesso_logado})

    matricula = request.POST.get("matricula", "").strip() or acesso_logado.matricula
    acesso = _acesso_por_matricula(matricula)
    if not acesso:
        return render(request, "solicitacoes/eventos_dia.html", {"erro": "Matrícula sem acesso institucional ativo.", "acesso_logado": acesso_logado})
    if acesso.usuario_id != request.user.id:
        return render(request, "solicitacoes/eventos_dia.html", {"erro": "A matrícula informada não corresponde ao usuário autenticado.", "acesso_logado": acesso_logado})

    hoje = timezone.localdate()
    eventos = _eventos_do_acesso(acesso, hoje)
    ids_eventos = list(eventos.values_list("id", flat=True))
    request.session["eventos_acesso_id"] = acesso.id
    request.session["eventos_matricula"] = acesso.matricula
    request.session["eventos_opos_autorizadas"] = ids_eventos

    return render(request, "solicitacoes/eventos_dia_resultado.html", {
        "eventos": eventos, "matricula": acesso.matricula, "acesso": acesso,
        "unidade": acesso.unidade, "data": hoje, "data_eventos": hoje,
    })


@login_required
def eventos_dia_resultado(request):
    acesso_id = request.session.get("eventos_acesso_id")
    if not acesso_id:
        return redirect("eventos_dia")

    acesso = (
        AcessoInstitucional.objects
        .select_related("usuario", "cpr", "unidade")
        .filter(id=acesso_id, ativo=True, usuario__is_active=True)
        .first()
    )
    if not acesso or acesso.usuario_id != request.user.id:
        for chave in ("eventos_acesso_id", "eventos_matricula", "eventos_opos_autorizadas"):
            request.session.pop(chave, None)
        messages.error(request, "Acesso não autorizado.")
        return redirect("login_gestao")

    hoje = timezone.localdate()
    eventos = _eventos_do_acesso(acesso, hoje)
    request.session["eventos_opos_autorizadas"] = list(eventos.values_list("id", flat=True))
    return render(request, "solicitacoes/eventos_dia_resultado.html", {
        "eventos": eventos, "perfil": acesso, "acesso": acesso,
        "matricula": acesso.matricula, "unidade": acesso.unidade,
        "data": hoje, "data_eventos": hoje,
    })
