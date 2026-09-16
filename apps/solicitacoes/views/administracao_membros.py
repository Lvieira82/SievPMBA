from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import CPR, PerfilUsuario, Unidade
from apps.solicitacoes.models_acesso import AcessoInstitucional
from .administracao_sistema import (
    UsuarioSistemaForm,
    _enviar_senha_inicial,
    _senha_inicial,
    _sincronizar_perfil_compat,
    administracao_sistema as administracao_sistema_gestor,
    usuario_editar as usuario_editar_gestor,
    usuario_novo as usuario_novo_gestor,
    usuario_senha as usuario_senha_gestor,
    usuario_desativar as usuario_desativar_gestor,
)


def _scope_membro(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return None
    acesso = getattr(request.user, "acesso_institucional", None)
    if not acesso or not acesso.ativo or acesso.funcao != "MEMBRO":
        return None
    if acesso.perfil == "CPR" and acesso.cpr_id:
        return {"desenvolvedor": False, "funcao": "MEMBRO", "perfil": "CPR", "cpr": acesso.cpr, "unidade": None}
    if acesso.perfil == "UNIDADE" and acesso.unidade_id:
        return {"desenvolvedor": False, "funcao": "MEMBRO", "perfil": "UNIDADE", "cpr": acesso.unidade.cpr, "unidade": acesso.unidade}
    if acesso.perfil == "COPPM":
        return {"desenvolvedor": False, "funcao": "MEMBRO", "perfil": "COPPM", "cpr": None, "unidade": None}
    return None


def _pode_gerenciar_operador(scope, acesso):
    if not scope or not acesso or acesso.funcao != "MEMBRO" or acesso.perfil != "OPERADOR":
        return False
    if scope["perfil"] == "COPPM":
        return True
    if scope["perfil"] == "CPR":
        return bool(acesso.cpr_id == scope["cpr"].id)
    if scope["perfil"] == "UNIDADE":
        return bool(acesso.unidade_id == scope["unidade"].id)
    return False


def _eh_membro(request):
    return _scope_membro(request) is not None


@login_required
def administracao_sistema(request):
    scope = _scope_membro(request)
    if not scope:
        return administracao_sistema_gestor(request)

    qs = AcessoInstitucional.objects.select_related("usuario", "cpr", "unidade").filter(perfil="OPERADOR", funcao="MEMBRO")
    if scope["perfil"] == "CPR":
        qs = qs.filter(cpr=scope["cpr"])
    elif scope["perfil"] == "UNIDADE":
        qs = qs.filter(unidade=scope["unidade"])
    return render(request, "administracao_sistema/index.html", {
        "acessos": qs.order_by("usuario__first_name", "matricula"),
        "perfis": qs,
        "scope": scope,
    })


@login_required
def usuario_novo(request):
    scope = _scope_membro(request)
    if not scope:
        return usuario_novo_gestor(request)

    if request.method == "POST":
        form = UsuarioSistemaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            unidade = data.get("unidade")
            if scope["perfil"] == "CPR":
                if not unidade or unidade.cpr_id != scope["cpr"].id:
                    form.add_error("unidade", "O operador deve pertencer ao seu CPR.")
            elif scope["perfil"] == "UNIDADE":
                if not unidade or unidade.id != scope["unidade"].id:
                    form.add_error("unidade", "O operador deve pertencer à sua Unidade.")
            if not form.errors:
                data["perfil"] = "OPERADOR"
                data["funcao"] = "MEMBRO"
                if unidade:
                    data["cpr"] = unidade.cpr
                senha = _senha_inicial(data["matricula"], "OPERADOR")
                try:
                    with transaction.atomic():
                        user = User.objects.create_user(
                            username=data["matricula"], email=data["email"],
                            password=senha, first_name=data["nome"], is_active=data["ativo"]
                        )
                        AcessoInstitucional.objects.create(
                            usuario=user, matricula=data["matricula"], cpf=data["cpf"],
                            telefone=data["telefone"], perfil="OPERADOR", funcao="MEMBRO",
                            cpr=data["cpr"], unidade=data["unidade"], primeiro_acesso=True,
                            ativo=data["ativo"]
                        )
                        _sincronizar_perfil_compat(user, data)
                        _enviar_senha_inicial(user, senha)
                except Exception:
                    if "user" in locals() and user.pk:
                        user.delete()
                    form.add_error(None, "Não foi possível concluir o cadastro ou enviar a senha para o e-mail informado.")
                else:
                    messages.success(request, "Operador criado. A senha inicial foi enviada para o e-mail cadastrado.")
                    return redirect("administracao_sistema")
    else:
        form = UsuarioSistemaForm()

    # Membro sempre cadastra operador; restringimos as unidades ao seu âmbito.
    form.fields["perfil"].initial = "OPERADOR"
    form.fields["perfil"].disabled = True
    form.fields["funcao"].initial = "MEMBRO"
    form.fields["funcao"].disabled = True
    if scope["perfil"] == "CPR":
        form.fields["unidade"].queryset = Unidade.objects.filter(cpr=scope["cpr"], ativo=True).order_by("nome")
        form.fields["cpr"].queryset = CPR.objects.filter(pk=scope["cpr"].id)
        form.fields["cpr"].initial = scope["cpr"].id
        form.fields["cpr"].disabled = True
    elif scope["perfil"] == "UNIDADE":
        form.fields["unidade"].queryset = Unidade.objects.filter(pk=scope["unidade"].id)
        form.fields["unidade"].initial = scope["unidade"].id
        form.fields["unidade"].disabled = True
        form.fields["cpr"].queryset = CPR.objects.filter(pk=scope["cpr"].id)
        form.fields["cpr"].initial = scope["cpr"].id
        form.fields["cpr"].disabled = True
    else:
        form.fields["unidade"].queryset = Unidade.objects.filter(ativo=True).select_related("cpr").order_by("nome")
        form.fields["cpr"].queryset = CPR.objects.filter(ativo=True).order_by("sigla")
        form.fields["cpr"].disabled = True
    return render(request, "administracao_sistema/form.html", {"form": form, "novo": True, "scope": scope})


@login_required
def usuario_editar(request, id):
    scope = _scope_membro(request)
    if not scope:
        return usuario_editar_gestor(request, id)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)
    if not _pode_gerenciar_operador(scope, acesso):
        messages.error(request, "Você não pode alterar este cadastro.")
        return redirect("administracao_sistema")
    if request.method == "POST":
        form = UsuarioSistemaForm(request.POST, instance=user)
        if form.is_valid():
            data = form.cleaned_data
            user.first_name = data["nome"]
            user.email = data["email"]
            user.is_active = data["ativo"]
            user.save(update_fields=["first_name", "email", "is_active"])
            acesso.matricula = data["matricula"]
            acesso.cpf = data["cpf"]
            acesso.telefone = data["telefone"]
            acesso.ativo = data["ativo"]
            acesso.save(update_fields=["matricula", "cpf", "telefone", "ativo", "atualizado_em"])
            _sincronizar_perfil_compat(user, {**data, "perfil": "OPERADOR", "funcao": "MEMBRO", "cpr": acesso.cpr, "unidade": acesso.unidade})
            messages.success(request, "Cadastro atualizado.")
            return redirect("administracao_sistema")
    else:
        form = UsuarioSistemaForm(instance=user)
    form.fields["perfil"].initial = "OPERADOR"
    form.fields["perfil"].disabled = True
    form.fields["funcao"].initial = "MEMBRO"
    form.fields["funcao"].disabled = True
    form.fields["cpr"].initial = acesso.cpr_id
    form.fields["cpr"].disabled = True
    form.fields["unidade"].queryset = Unidade.objects.filter(pk=acesso.unidade_id)
    form.fields["unidade"].initial = acesso.unidade_id
    form.fields["unidade"].disabled = True
    return render(request, "administracao_sistema/form.html", {"form": form, "novo": False, "usuario": user, "scope": scope})


@login_required
def usuario_ativar(request, id):
    scope = _scope_membro(request)
    if not scope:
        from .administracao_acoes import usuario_ativar as ativar_gestor
        return ativar_gestor(request, id)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)
    if not _pode_gerenciar_operador(scope, acesso):
        messages.error(request, "Você não pode ativar este cadastro.")
        return redirect("administracao_sistema")
    acesso.ativo = True
    acesso.save(update_fields=["ativo", "atualizado_em"])
    user.is_active = True
    user.save(update_fields=["is_active"])
    messages.success(request, "Usuário ativado.")
    return redirect("administracao_sistema")


@login_required
def usuario_desativar(request, id):
    scope = _scope_membro(request)
    if not scope:
        return usuario_desativar_gestor(request, id)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)
    if not _pode_gerenciar_operador(scope, acesso):
        messages.error(request, "Você não pode desativar este cadastro.")
        return redirect("administracao_sistema")
    acesso.ativo = False
    acesso.save(update_fields=["ativo", "atualizado_em"])
    user.is_active = False
    user.save(update_fields=["is_active"])
    messages.success(request, "Usuário desativado.")
    return redirect("administracao_sistema")


@login_required
def usuario_excluir(request, id):
    scope = _scope_membro(request)
    if not scope:
        from .administracao_acoes import usuario_excluir as excluir_gestor
        return excluir_gestor(request, id)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)
    if user.is_superuser or not _pode_gerenciar_operador(scope, acesso):
        messages.error(request, "Você não pode excluir este cadastro.")
        return redirect("administracao_sistema")
    user.delete()
    messages.success(request, "Operador excluído definitivamente.")
    return redirect("administracao_sistema")


@login_required
def usuario_senha(request, id):
    scope = _scope_membro(request)
    if not scope:
        return usuario_senha_gestor(request, id)
    messages.error(request, "A redefinição de senha continua restrita ao administrador.")
    return redirect("administracao_sistema")
