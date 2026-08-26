from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.permissoes import pode_aprovar_solicitacao, pode_ver_solicitacao
from .operacional import gerar_opo as gerar_opo_original


@login_required
def aprovacoes(request):
    if not request.user.is_superuser and not request.user.is_staff:
        acesso = getattr(request.user, "acesso_institucional", None)
        if not acesso or not acesso.ativo or acesso.funcao != "GESTOR":
            messages.error(request, "Somente gestores podem acessar as aprovações.")
            return redirect("painel_gestao")

    solicitacoes = Solicitacao.objects.filter(status="PENDENTE").select_related(
        "municipio", "bairro", "unidade", "tipo_evento"
    ).prefetch_related("documentos").order_by("data_evento", "hora_inicio")

    if not (request.user.is_superuser or request.user.is_staff):
        permitidas = [s.id for s in solicitacoes if pode_aprovar_solicitacao(request.user, s)]
        solicitacoes = solicitacoes.filter(id__in=permitidas)

    return render(request, "gestao/aprovacoes.html", {
        "solicitacoes": solicitacoes,
        "pode_aprovar": True,
    })


@login_required
def aprovar_solicitacao(request, id):
    if request.method != "POST":
        return redirect("aprovacoes")

    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)

    if not pode_aprovar_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para aprovar esta solicitação.")
        return redirect("aprovacoes")

    if solicitacao.status != "PENDENTE":
        messages.error(request, "Esta solicitação não está pendente de aprovação.")
        return redirect("aprovacoes")

    if not solicitacao.documentos.exists():
        messages.error(request, "Não é possível aprovar: a solicitação ainda não possui documentos anexados.")
        return redirect("aprovacoes")

    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()
    solicitacao.aprovado_por = request.user.get_full_name() or request.user.username
    solicitacao.save(update_fields=["status", "data_aprovacao", "aprovado_por", "atualizado_em"])

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        status="APROVADA",
        observacao="Solicitação aprovada após conferência dos documentos anexados.",
    )

    messages.success(request, f"Solicitação {solicitacao.protocolo} aprovada. Gerando OPO...")
    return redirect("gerar_opo", id=id)


@login_required
def solicitar_correcao_gestao(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)

    if not pode_aprovar_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para solicitar correção desta solicitação.")
        return redirect("aprovacoes")

    if not solicitacao.documentos.exists():
        messages.error(request, "Não é possível mandar para correção: a solicitação ainda não possui documentos anexados.")
        return redirect("aprovacoes")

    if request.method == "POST":
        motivo = request.POST.get("motivo_correcao", "").strip()
        if not motivo:
            messages.error(request, "Informe o motivo da correção.")
            return render(request, "solicitacoes/solicitar_correcao.html", {"solicitacao": solicitacao})

        solicitacao.status = "CORRECAO"
        solicitacao.motivo_correcao = motivo
        solicitacao.save(update_fields=["status", "motivo_correcao", "atualizado_em"])
        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            status="CORRECAO",
            observacao=motivo,
        )
        messages.success(request, "Solicitação enviada para correção.")
        return redirect("aprovacoes")

    return render(request, "solicitacoes/solicitar_correcao.html", {"solicitacao": solicitacao})


@login_required
def gerar_opo_seguro(request, id):
    solicitacao = get_object_or_404(Solicitacao.objects.select_related("unidade"), pk=id)
    if not pode_aprovar_solicitacao(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para gerar esta OPO.")
        return redirect("painel_gestao")
    if not solicitacao.documentos.exists():
        messages.error(request, "A OPO não pode ser gerada sem documentos anexados.")
        return redirect("aprovacoes")
    return gerar_opo_original(request, id)
