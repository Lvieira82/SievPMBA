from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


GROUP_MEMBRO = "SIEV_MEMBRO"
GROUP_OPERADOR = "SIEV_OPERADOR"


def membro_ou_gestor(view_func):
    """Permite desenvolvedor/gestores e membros, mas bloqueia operadores."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect("login_gestao")
        if user.is_superuser or user.is_staff:
            return view_func(request, *args, **kwargs)
        perfil = getattr(user, "perfil_siev", None)
        if not perfil or not perfil.ativo:
            messages.error(request, "Usuário sem perfil institucional ativo.")
            return redirect("login_gestao")
        if user.groups.filter(name=GROUP_OPERADOR).exists():
            messages.error(request, "Esta função não está disponível para operadores.")
            return redirect("painel_gestao")
        return view_func(request, *args, **kwargs)
    return wrapper


def somente_operacional(view_func):
    """Permite membro/operador da unidade e gestores da própria unidade."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect("login_gestao")
        if user.is_superuser or user.is_staff:
            return view_func(request, *args, **kwargs)
        perfil = getattr(user, "perfil_siev", None)
        if not perfil or not perfil.ativo or perfil.perfil != "UNIDADE" or not perfil.unidade_id:
            messages.error(request, "Acesso não autorizado.")
            return redirect("painel_gestao")
        return view_func(request, *args, **kwargs)
    return wrapper
