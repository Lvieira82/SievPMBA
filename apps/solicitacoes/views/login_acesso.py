from django.urls import reverse

from apps.solicitacoes.models_acesso import AcessoInstitucional
from .acesso import login_gestao as login_gestao_original


def login_gestao(request):
    if request.method == "POST":
        matricula = (request.POST.get("username") or "").strip()
        acesso = AcessoInstitucional.objects.filter(
            matricula__iexact=matricula,
            perfil="OPERADOR",
            ativo=True,
        ).first()
        if acesso:
            dados = request.POST.copy()
            dados["next"] = reverse("eventos_dia")
            request.POST = dados

    return login_gestao_original(request)
