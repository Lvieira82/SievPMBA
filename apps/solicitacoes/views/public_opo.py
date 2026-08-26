from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import AnexoOPO, MatriculaAutorizada, Solicitacao


def _opo_autorizada_na_sessao(request, id):
    ids = request.session.get("eventos_opos_autorizadas", [])
    return int(id) in [int(valor) for valor in ids]


def validar_matricula_opo_publica(request, id):
    solicitacao = get_object_or_404(Solicitacao, pk=id)

    # Se a OPO foi liberada pela consulta "Eventos do Dia", não pede a
    # matrícula novamente.
    if _opo_autorizada_na_sessao(request, id):
        request.session[f"opo_autorizada_{id}"] = True
        return redirect("detalhe_opo_publica", id=id)

    if request.method == "POST":
        matricula = "".join((request.POST.get("matricula") or "").split())
        autorizado = MatriculaAutorizada.objects.filter(matricula=matricula, ativo=True).first()
        if autorizado:
            request.session[f"opo_autorizada_{id}"] = True
            return redirect("detalhe_opo_publica", id=id)
        messages.error(request, "Matrícula não autorizada para consulta desta OPO.")

    return render(request, "gestao/validar_matricula_opo.html", {"solicitacao": solicitacao})


def detalhe_opo_publica(request, id):
    if not request.session.get(f"opo_autorizada_{id}") and not _opo_autorizada_na_sessao(request, id):
        return redirect("validar_matricula_opo_publica", id=id)

    solicitacao = get_object_or_404(Solicitacao, pk=id)
    anexos = AnexoOPO.objects.filter(solicitacao=solicitacao).order_by("-criado_em")
    return render(request, "gestao/detalhe_opo_publica.html", {"solicitacao": solicitacao, "anexos": anexos})


def abrir_opo_publica(request, id):
    if not request.session.get(f"opo_autorizada_{id}") and not _opo_autorizada_na_sessao(request, id):
        raise Http404("Acesso não autorizado.")

    anexo = AnexoOPO.objects.filter(solicitacao_id=id).order_by("-criado_em").first()
    if not anexo or not anexo.arquivo:
        raise Http404("OPO não encontrada.")

    return FileResponse(anexo.arquivo.open("rb"), content_type="application/pdf")
