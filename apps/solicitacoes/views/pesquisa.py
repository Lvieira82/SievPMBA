from django.core import signing
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao


def responder_pesquisa(request, token):
    try:
        dados = signing.loads(token, salt="sievpm-pesquisa", max_age=60 * 60 * 24 * 90)
    except signing.BadSignature:
        return render(request, "pesquisa/obrigado.html", {"invalida": True})

    protocolo = dados.get("protocolo")
    solicitacao = get_object_or_404(Solicitacao, protocolo=protocolo)

    if request.method == "POST":
        try:
            nota = int(request.POST.get("nota", ""))
        except (TypeError, ValueError):
            nota = 0

        comentario = (request.POST.get("comentario") or "").strip()
        if nota not in range(1, 6):
            return render(request, "pesquisa/responder.html", {
                "solicitacao": solicitacao,
                "erro": "Selecione uma nota de 1 a 5.",
                "nota": nota,
                "comentario": comentario,
            })

        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            acao="PESQUISA RESPONDIDA",
            observacao=(
                f"Nota: {nota}/5. "
                f"Comentário: {comentario or 'Sem comentário.'}"
            ),
        )
        return render(request, "pesquisa/obrigado.html", {"invalida": False})

    return render(request, "pesquisa/responder.html", {"solicitacao": solicitacao})
