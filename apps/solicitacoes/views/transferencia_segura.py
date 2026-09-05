from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import Solicitacao, TransferenciaSolicitacao, Unidade, HistoricoSolicitacao
from apps.solicitacoes.permissoes import pode_transferir


@login_required
def transferir_solicitacao_seguro(request, id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related("unidade", "municipio", "bairro"),
        pk=id,
    )

    if not pode_transferir(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para transferir esta solicitação.")
        return redirect("aprovacoes")

    unidades = Unidade.objects.filter(ativo=True).exclude(pk=solicitacao.unidade_id).select_related("cpr").order_by("sigla", "nome")

    if request.method == "POST":
        unidade_id = request.POST.get("unidade_destino")
        motivo = (request.POST.get("motivo") or "").strip()

        unidade_destino = get_object_or_404(Unidade, pk=unidade_id, ativo=True)
        if unidade_destino.pk == solicitacao.unidade_id:
            messages.error(request, "A unidade de destino deve ser diferente da unidade atual.")
            return render(request, "gestao/transferir_solicitacao.html", {"solicitacao": solicitacao, "unidades": unidades})

        unidade_origem = solicitacao.unidade
        with transaction.atomic():
            TransferenciaSolicitacao.objects.create(
                solicitacao=solicitacao,
                unidade_origem=unidade_origem,
                unidade_destino=unidade_destino,
                usuario=request.user,
                motivo=motivo,
            )
            solicitacao.unidade = unidade_destino
            solicitacao.origem = "TRANSFERIDA"
            solicitacao.save(update_fields=["unidade", "origem", "atualizado_em"])
            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=request.user,
                acao="TRANSFERÊNCIA DE UNIDADE",
                status=solicitacao.status,
                observacao=(f"Transferida de {unidade_origem} para {unidade_destino}." + (f" Motivo: {motivo}" if motivo else "")),
            )

        messages.success(request, f"Solicitação {solicitacao.protocolo} transferida para {unidade_destino} com toda a documentação preservada.")
        return redirect("aprovacoes")

    return render(request, "gestao/transferir_solicitacao.html", {"solicitacao": solicitacao, "unidades": unidades})
