from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from apps.solicitacoes.models import AnexoOPO


def abrir_opo_publica(request, id):
    if not request.session.get(f"opo_autorizada_{id}"):
        raise Http404("Acesso não autorizado.")

    anexo = AnexoOPO.objects.filter(
        solicitacao_id=id
    ).order_by("-criado_em").first()

    if not anexo or not anexo.arquivo:
        raise Http404("OPO não encontrada.")

    return FileResponse(
        anexo.arquivo.open("rb"),
        content_type="application/pdf",
    )
