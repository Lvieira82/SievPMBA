from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404, render

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao


MARCADOR_RESPOSTA = "PESQUISA RESPONDIDA"


def _ja_respondida(solicitacao):
    return HistoricoSolicitacao.objects.filter(
        solicitacao=solicitacao,
        acao=MARCADOR_RESPOSTA,
    ).exists()


def responder_pesquisa(request, token):
    try:
        dados = signing.loads(token, salt="sievpm-pesquisa", max_age=60 * 60 * 24 * 90)
    except signing.BadSignature:
        return render(request, "pesquisa/obrigado.html", {"invalida": True})

    protocolo = dados.get("protocolo")
    solicitacao = get_object_or_404(Solicitacao, protocolo=protocolo)

    if request.method == "GET" and _ja_respondida(solicitacao):
        return render(request, "pesquisa/obrigado.html", {"ja_respondida": True})

    if request.method == "POST":
        try:
            nota_sistema = int(request.POST.get("nota_sistema", ""))
        except (TypeError, ValueError):
            nota_sistema = 0

        try:
            nota_atendimento = int(request.POST.get("nota_atendimento", ""))
        except (TypeError, ValueError):
            nota_atendimento = 0

        comentario = (request.POST.get("comentario") or "").strip()

        if nota_sistema not in range(1, 6) or nota_atendimento not in range(1, 6):
            return render(request, "pesquisa/responder.html", {
                "solicitacao": solicitacao,
                "erro": "Selecione uma nota de 1 a 5 para cada pergunta.",
                "nota_sistema": nota_sistema,
                "nota_atendimento": nota_atendimento,
                "comentario": comentario,
            })

        with transaction.atomic():
            solicitacao_bloqueada = Solicitacao.objects.select_for_update().get(pk=solicitacao.pk)

            if HistoricoSolicitacao.objects.filter(
                solicitacao=solicitacao_bloqueada,
                acao=MARCADOR_RESPOSTA,
            ).exists():
                return render(request, "pesquisa/obrigado.html", {"ja_respondida": True})

            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao_bloqueada,
                acao=MARCADOR_RESPOSTA,
                observacao=(
                    f"Nota Sistema: {nota_sistema}/5. "
                    f"Nota Atendimento: {nota_atendimento}/5. "
                    f"Comentário: {comentario or 'Sem comentário.'}"
                ),
            )

        return render(request, "pesquisa/obrigado.html", {"invalida": False})

    return render(request, "pesquisa/responder.html", {"solicitacao": solicitacao})
