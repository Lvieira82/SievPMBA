from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.solicitacoes.models import COPPM, CPR, Unidade


@login_required
def visao_desenvolvedor(request):
    """Permite ao superusuário escolher o âmbito institucional para visualizar o painel."""
    if not request.user.is_superuser:
        messages.error(request, "Esta função é exclusiva do desenvolvedor.")
        return redirect("painel_gestao")

    if request.method == "POST":
        tipo = (request.POST.get("tipo") or "").strip().upper()
        objeto_id = (request.POST.get("objeto_id") or "").strip()

        modelos = {
            "COPPM": COPPM,
            "CPR": CPR,
            "UNIDADE": Unidade,
        }
        modelo = modelos.get(tipo)
        if not modelo or not objeto_id:
            messages.error(request, "Selecione o âmbito e o cadastro desejado.")
            return redirect("visao_desenvolvedor")

        objeto = modelo.objects.filter(pk=objeto_id, ativo=True).first()
        if not objeto:
            messages.error(request, "O cadastro selecionado não existe ou está inativo.")
            return redirect("visao_desenvolvedor")

        request.session["siev_visao_desenvolvedor"] = {
            "tipo": tipo,
            "id": objeto.pk,
            "rotulo": str(objeto),
        }
        messages.success(request, f"Visão selecionada: {objeto}.")
        return redirect("painel_gestao")

    return render(request, "gestao/visao_desenvolvedor.html", {
        "coppms": COPPM.objects.filter(ativo=True).order_by("sigla"),
        "cprs": CPR.objects.filter(ativo=True).select_related("coppm").order_by("sigla"),
        "unidades": Unidade.objects.filter(ativo=True).select_related("cpr").order_by("sigla"),
    })


@login_required
def sair_visao_desenvolvedor(request):
    if not request.user.is_superuser:
        messages.error(request, "Esta função é exclusiva do desenvolvedor.")
        return redirect("painel_gestao")
    request.session.pop("siev_visao_desenvolvedor", None)
    messages.success(request, "Você voltou à visão geral do SiEv.")
    return redirect("painel_gestao")
