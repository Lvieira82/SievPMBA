from django.shortcuts import redirect

from .administracao import painel_gestao as painel_gestao_original


def painel_gestao(request):
    if request.user.is_authenticated and not (request.user.is_superuser or request.user.is_staff):
        acesso = getattr(request.user, "acesso_institucional", None)
        if acesso and acesso.ativo and acesso.perfil == "OPERADOR":
            return redirect("eventos_dia")

    return painel_gestao_original(request)
