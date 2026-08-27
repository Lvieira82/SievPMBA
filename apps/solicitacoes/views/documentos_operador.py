from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import (
    ConfiguracaoUnidade,
    DocumentoSolicitacao,
    HistoricoSolicitacao,
    Solicitacao,
)
from .compat import (
    abrir_documento_solicitacao as _abrir_documento_original,
    gerar_opo as _gerar_opo_original,
)


def _perfil_e_escopo(request):
    if request.user.is_superuser or request.user.is_staff:
        return None, Solicitacao.objects.all()

    perfil = getattr(request.user, "perfil_siev", None)
    if not perfil or not perfil.ativo:
        return None, Solicitacao.objects.none()

    if perfil.perfil == "COPPM":
        return perfil, Solicitacao.objects.all()

    if perfil.perfil == "CPR":
        return perfil, Solicitacao.objects.filter(unidade__cpr=perfil.cpr)

    if perfil.perfil == "UNIDADE":
        return perfil, Solicitacao.objects.filter(unidade=perfil.unidade)

    return None, Solicitacao.objects.none()


def _documentacao(solicitacao):
    """Calcula a situação documental sem alterar o banco de dados."""
    documentos = list(
        DocumentoSolicitacao.objects
        .filter(solicitacao=solicitacao)
        .select_related("tipo_documento")
    )

    obrigatorios = []
    if solicitacao.unidade_id:
        obrigatorios = list(
            ConfiguracaoUnidade.objects
            .filter(
                unidade_id=solicitacao.unidade_id,
                ativo=True,
                obrigatorio=True,
                tipo_documento__isnull=False,
            )
            .select_related("tipo_documento")
        )

    tipos_anexados = {documento.tipo_documento_id for documento in documentos}
    faltantes = [
        item.tipo_documento.nome
        for item in obrigatorios
        if item.tipo_documento_id not in tipos_anexados
    ]

    # A documentação é condição para a OPO: deve existir pelo menos
    # um documento e, quando houver configuração de obrigatórios,
    # todos eles precisam estar presentes.
    ok = bool(documentos) and not faltantes

    return {
        "documentos": documentos,
        "obrigatorios": obrigatorios,
        "faltantes": faltantes,
        "ok": ok,
    }


def _anexar_status_documental(solicitacao):
    status = _documentacao(solicitacao)
    solicitacao.documentos = status["documentos"]
    solicitacao.documentos_obrigatorios = status["obrigatorios"]
    solicitacao.documentos_faltantes = status["faltantes"]
    solicitacao.documentacao_ok = status["ok"]
    return solicitacao


@login_required
def aprovacoes(request):
    perfil, escopo = _perfil_e_escopo(request)

    if not (request.user.is_superuser or request.user.is_staff) and perfil is None:
        messages.error(request, "Usuário sem perfil institucional ativo.")
        return redirect("login_gestao")

    solicitacoes = (
        escopo
        .filter(status="PENDENTE")
        .select_related("unidade", "municipio", "bairro", "tipo_evento", "usuario")
        .order_by("data_evento", "hora_inicio")
    )

    for solicitacao in solicitacoes:
        _anexar_status_documental(solicitacao)

    return render(
        request,
        "gestao/aprovacoes.html",
        {"solicitacoes": solicitacoes, "perfil": perfil},
    )


@login_required
def documentos_solicitacao(request, id):
    perfil, escopo = _perfil_e_escopo(request)

    if not (request.user.is_superuser or request.user.is_staff) and perfil is None:
        messages.error(request, "Acesso não autorizado.")
        return redirect("login_gestao")

    solicitacao = get_object_or_404(
        escopo.select_related("municipio", "bairro", "unidade", "tipo_evento"),
        pk=id,
    )
    status = _documentacao(solicitacao)

    return render(
        request,
        "gestao/documentos_solicitacao.html",
        {
            "solicitacao": solicitacao,
            "documentos": status["documentos"],
            "documentos_obrigatorios": status["obrigatorios"],
            "documentos_faltantes": status["faltantes"],
            "documentacao_ok": status["ok"],
        },
    )


@login_required
def abrir_documento_solicitacao(request, id, tipo):
    """Só permite abrir um PDF pertencente ao escopo institucional do operador."""
    _, escopo = _perfil_e_escopo(request)
    documento = get_object_or_404(
        DocumentoSolicitacao.objects.select_related("solicitacao"),
        pk=id,
        solicitacao__in=escopo,
    )
    return _abrir_documento_original(request, documento.id, tipo)


@login_required
def aprovar_solicitacao(request, id):
    if request.method != "POST":
        return redirect("aprovacoes")

    perfil, escopo = _perfil_e_escopo(request)

    if not (request.user.is_superuser or request.user.is_staff) and perfil is None:
        messages.error(request, "Acesso não autorizado.")
        return redirect("login_gestao")

    solicitacao = get_object_or_404(escopo, pk=id)

    if solicitacao.status != "PENDENTE":
        messages.error(request, "Esta solicitação não está pendente de análise.")
        return redirect("aprovacoes")

    status_documental = _documentacao(solicitacao)
    if not status_documental["ok"]:
        if status_documental["faltantes"]:
            faltantes = ", ".join(status_documental["faltantes"])
            messages.error(request, f"OPO bloqueada: falta(m) documento(s) obrigatório(s): {faltantes}.")
        else:
            messages.error(request, "OPO bloqueada: a solicitação ainda não possui documento anexado.")
        return redirect("documentos_solicitacao", id=id)

    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.aprovado_por = request.user.get_full_name() or request.user.username
    solicitacao.save(update_fields=["status", "data_aprovacao", "aprovado_por", "atualizado_em"])

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        status="APROVADA",
        observacao="Solicitação aprovada após conferência da documentação para geração da OPO.",
    )

    messages.success(request, f"Solicitação {solicitacao.protocolo} aprovada. A OPO está liberada para geração.")
    return redirect("aprovacoes")


@login_required
def gerar_opo(request, id):
    """Última barreira: nenhuma OPO é gerada sem documentação conferida."""
    _, escopo = _perfil_e_escopo(request)
    solicitacao = get_object_or_404(escopo, pk=id)
    status_documental = _documentacao(solicitacao)

    if not status_documental["ok"]:
        if status_documental["faltantes"]:
            faltantes = ", ".join(status_documental["faltantes"])
            messages.error(request, f"OPO bloqueada: falta(m) documento(s) obrigatório(s): {faltantes}.")
        else:
            messages.error(request, "OPO bloqueada: a solicitação não possui documento anexado.")
        return redirect("documentos_solicitacao", id=id)

    return _gerar_opo_original(request, id)
