from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect

from .administracao_sistema import _escopo, _pode_gerenciar


@login_required
def usuario_ativar(request, id):
    scope = _escopo(request)
    if not scope or not scope["desenvolvedor"]:
        messages.error(request, "Somente o desenvolvedor pode ativar usuários.")
        return redirect("administracao_sistema")

    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)
    if not acesso or not _pode_gerenciar(scope, acesso):
        messages.error(request, "Este cadastro não possui vínculo institucional válido.")
        return redirect("administracao_sistema")

    acesso.ativo = True
    acesso.save(update_fields=["ativo", "atualizado_em"])
    user.is_active = True
    user.save(update_fields=["is_active"])

    messages.success(request, "Usuário ativado.")
    return redirect("administracao_sistema")


@login_required
def usuario_excluir(request, id):
    scope = _escopo(request)
    if not scope or not scope["desenvolvedor"]:
        messages.error(request, "Somente o desenvolvedor pode excluir usuários.")
        return redirect("administracao_sistema")

    user = get_object_or_404(User, pk=id)
    if user.is_superuser:
        messages.error(request, "O usuário desenvolvedor não pode ser excluído por esta tela.")
        return redirect("administracao_sistema")

    acesso = getattr(user, "acesso_institucional", None)
    if not acesso or not _pode_gerenciar(scope, acesso):
        messages.error(request, "Este cadastro não possui vínculo institucional válido.")
        return redirect("administracao_sistema")

    matricula = acesso.matricula
    nome = user.get_full_name() or user.username
    user.delete()

    messages.success(request, f"Registro de {nome} ({matricula}) excluído definitivamente.")
    return redirect("administracao_sistema")
