from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.solicitacoes.models import Solicitacao


@login_required
def minhas_solicitacoes(request):
    """Lista as solicitações registradas pelo usuário autenticado."""
    solicitacoes = (
        Solicitacao.objects
        .filter(usuario=request.user)
        .select_related("municipio", "bairro", "unidade", "tipo_evento")
        .order_by("-criado_em")
    )

    return render(
        request,
        "gestao/minhas_solicitacoes.html",
        {"solicitacoes": solicitacoes},
    )
