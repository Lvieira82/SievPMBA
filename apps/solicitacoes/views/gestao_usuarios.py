from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import PerfilUsuario, MatriculaAutorizada, CPR, Unidade
from apps.solicitacoes.models_acesso import AcessoInstitucional
from apps.solicitacoes.permissoes import pode_administrar_usuarios


def _desenvolvedor(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def _acesso(user):
    if _desenvolvedor(user):
        return None
    acesso = getattr(user, "acesso_institucional", None)
    if not acesso or not acesso.ativo or not user.is_active:
        return None
    return acesso


def _pode_ver_alvo(request_user, alvo):
    if _desenvolvedor(request_user):
        return True
    acesso = _acesso(request_user)
    if not acesso or alvo.usuario_id == request_user.id:
        return False
    if acesso.funcao not in {"GESTOR", "MEMBRO"}:
        return False
    if acesso.perfil == "COPPM":
        return alvo.perfil in {"COPPM", "CPR", "UNIDADE", "OPERADOR"}
    if acesso.perfil == "CPR":
        if alvo.perfil == "CPR":
            return alvo.cpr_id == acesso.cpr_id
        return bool(alvo.perfil in {"UNIDADE", "OPERADOR"} and alvo.unidade_id and Unidade.objects.filter(pk=alvo.unidade_id, cpr_id=acesso.cpr_id, ativo=True).exists())
    if acesso.perfil == "UNIDADE":
        return bool(alvo.perfil in {"UNIDADE", "OPERADOR"} and alvo.unidade_id == acesso.unidade_id)
    return False


def _pode_criar(request_user, perfil, funcao, cpr=None, unidade=None):
    if _desenvolvedor(request_user):
        return True
    acesso = _acesso(request_user)
    if not acesso or acesso.funcao not in {"GESTOR", "MEMBRO"}:
        return False

    if perfil == "OPERADOR":
        if not unidade:
            return False
        if acesso.perfil == "COPPM":
            return True
        if acesso.perfil == "CPR":
            return unidade.cpr_id == acesso.cpr_id
        if acesso.perfil == "UNIDADE":
            return unidade.id == acesso.unidade_id
        return False

    if funcao not in {"GESTOR", "MEMBRO"}:
        return False
    if acesso.funcao == "MEMBRO" and funcao != "MEMBRO":
        return False

    if acesso.perfil == "COPPM":
        return perfil in {"COPPM", "CPR", "UNIDADE"}
    if acesso.perfil == "CPR":
        if perfil == "CPR":
            return bool(cpr and cpr.id == acesso.cpr_id)
        if perfil == "UNIDADE":
            return bool(unidade and unidade.cpr_id == acesso.cpr_id)
        return False
    if acesso.perfil == "UNIDADE":
        return perfil == "UNIDADE" and bool(unidade and unidade.id == acesso.unidade_id)
    return False


def _escopo_cadastro(user):
    if _desenvolvedor(user):
        return CPR.objects.filter(ativo=True).order_by("sigla"), Unidade.objects.filter(ativo=True).select_related("cpr").order_by("sigla")
    acesso = _acesso(user)
    if not acesso:
        return CPR.objects.none(), Unidade.objects.none()
    if acesso.perfil == "COPPM":
        return CPR.objects.filter(ativo=True).order_by("sigla"), Unidade.objects.filter(ativo=True).select_related("cpr").order_by("sigla")
    if acesso.perfil == "CPR":
        return CPR.objects.filter(id=acesso.cpr_id, ativo=True), Unidade.objects.filter(cpr_id=acesso.cpr_id, ativo=True).order_by("sigla")
    if acesso.perfil == "UNIDADE":
        return CPR.objects.filter(id=acesso.unidade.cpr_id, ativo=True), Unidade.objects.filter(id=acesso.unidade_id, ativo=True)
    return CPR.objects.none(), Unidade.objects.none()


def _alvos_usuario(user):
    qs = AcessoInstitucional.objects.select_related("usuario", "cpr", "unidade")
    if _desenvolvedor(user):
        return qs.order_by("usuario__first_name", "usuario__last_name")
    acesso = _acesso(user)
    if not acesso or acesso.funcao not in {"GESTOR", "MEMBRO"}:
        return qs.none()
    if acesso.perfil == "COPPM":
        return qs.order_by("usuario__first_name", "usuario__last_name")
    if acesso.perfil == "CPR":
        return qs.filter(cpr_id=acesso.cpr_id).order_by("usuario__first_name", "usuario__last_name")
    if acesso.perfil == "UNIDADE":
        return qs.filter(unidade_id=acesso.unidade_id).order_by("usuario__first_name", "usuario__last_name")
    return qs.none()


def _rotulo_perfil(acesso):
    if acesso.perfil == "OPERADOR":
        return "Operador"
    return f"{acesso.get_funcao_display()} {acesso.get_perfil_display()}"


def _form_context(request, form_data=None, erro=None):
    cprs, unidades = _escopo_cadastro(request.user)
    return {"form_data": form_data or {}, "cprs": cprs, "unidades": unidades, "desenvolvedor": _desenvolvedor(request.user), "erro": erro}


@login_required
def usuarios_unidade_novo(request):
    if not pode_administrar_usuarios(request.user):
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")

    if request.method == "POST":
        data = request.POST
        tipo_perfil = data.get("perfil_acesso", "MEMBRO").strip().upper()
        ambito = data.get("perfil", "").strip().upper()
        funcao = data.get("funcao", "MEMBRO").strip().upper()
        nome = data.get("nome", "").strip()
        matricula = data.get("matricula", "").strip()
        posto = data.get("posto", "").strip()
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        senha = data.get("senha", "")
        confirmacao = data.get("confirmar_senha", "")
        cpr_id = data.get("cpr") or None
        unidade_id = data.get("unidade") or None

        if not nome or not matricula or not username or not senha:
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Preencha os campos obrigatórios."))
        if senha != confirmacao:
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "As senhas não conferem."))
        if len(senha) < 6:
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "A senha deve possuir pelo menos 6 caracteres."))
        if User.objects.filter(username=username).exists():
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Este nome de usuário já existe."))
        if AcessoInstitucional.objects.filter(matricula=matricula).exists() or MatriculaAutorizada.objects.filter(matricula=matricula, ativo=True).exists():
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Esta matrícula já está cadastrada."))
        if tipo_perfil not in {"MEMBRO", "OPERADOR"}:
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Selecione um perfil válido."))
        if ambito not in {"COPPM", "CPR", "UNIDADE"}:
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Selecione um âmbito válido."))

        if tipo_perfil == "OPERADOR":
            perfil_destino = "OPERADOR"
            funcao = "MEMBRO"
        else:
            perfil_destino = ambito
            if funcao not in {"GESTOR", "MEMBRO"}:
                return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Selecione uma função válida."))

        cpr = get_object_or_404(CPR, id=cpr_id, ativo=True) if cpr_id else None
        unidade = get_object_or_404(Unidade, id=unidade_id, ativo=True) if unidade_id else None
        if unidade:
            cpr = unidade.cpr

        if perfil_destino == "COPPM":
            cpr = None
            unidade = None
        elif perfil_destino == "CPR" and not cpr:
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Selecione o CPR."))
        elif perfil_destino in {"UNIDADE", "OPERADOR"} and not unidade:
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Selecione a Unidade."))

        if not _pode_criar(request.user, perfil_destino, funcao, cpr, unidade):
            return render(request, "gestao/cadastrar_usuario.html", _form_context(request, data, "Você não possui permissão para criar este usuário nesse âmbito."))

        with transaction.atomic():
            user = User.objects.create_user(username=username, email=email, password=senha, first_name=nome)
            partes = nome.split()
            user.first_name = partes[0]
            user.last_name = " ".join(partes[1:])
            user.save(update_fields=["first_name", "last_name"])

            AcessoInstitucional.objects.create(
                usuario=user,
                matricula=matricula,
                cpf=None,
                telefone="",
                perfil=perfil_destino,
                funcao=funcao,
                cpr=cpr,
                unidade=unidade,
                primeiro_acesso=True,
                ativo=True,
            )

            PerfilUsuario.objects.update_or_create(
                usuario=user,
                defaults={
                    "perfil": "UNIDADE" if perfil_destino == "OPERADOR" else perfil_destino,
                    "cpr": cpr,
                    "unidade": unidade,
                    "ativo": True,
                },
            )

            MatriculaAutorizada.objects.create(matricula=matricula, nome=nome, posto=posto, unidade=unidade, ativo=True)

        messages.success(request, "Usuário cadastrado com sucesso.")
        return redirect("usuarios_unidade")

    return render(request, "gestao/cadastrar_usuario.html", _form_context(request))


@login_required
def usuarios_unidade_nova_lista(request):
    if not pode_administrar_usuarios(request.user):
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")

    acesso = _acesso(request.user)
    usuarios = list(_alvos_usuario(request.user))
    for item in usuarios:
        item.rotulo_perfil = _rotulo_perfil(item)
        item.pode_editar = _pode_ver_alvo(request.user, item)
        item.pode_senha = item.pode_editar
        item.pode_excluir = item.pode_editar
        item.pode_desativar = item.pode_editar and item.ativo

    return render(request, "gestao/usuarios_unidade.html", {"usuarios": usuarios, "perfil": acesso, "desenvolvedor": _desenvolvedor(request.user)})


@login_required
def usuarios_unidade_novo_editar(request, id):
    if not pode_administrar_usuarios(request.user):
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")

    alvo = get_object_or_404(AcessoInstitucional.objects.select_related("usuario", "cpr", "unidade"), id=id)
    if not _pode_ver_alvo(request.user, alvo):
        messages.error(request, "Você não possui acesso a este usuário.")
        return redirect("usuarios_unidade")

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        matricula = request.POST.get("matricula", "").strip()
        if not nome or not username or not matricula:
            messages.error(request, "Nome, usuário e matrícula são obrigatórios.")
            return redirect("editar_usuario_unidade", id=id)
        if User.objects.filter(username=username).exclude(id=alvo.usuario_id).exists():
            messages.error(request, "Este nome de usuário já está sendo utilizado.")
            return redirect("editar_usuario_unidade", id=id)
        if AcessoInstitucional.objects.filter(matricula=matricula).exclude(id=alvo.id).exists():
            messages.error(request, "Esta matrícula já está sendo utilizada.")
            return redirect("editar_usuario_unidade", id=id)

        antiga_matricula = alvo.matricula
        alvo.usuario.username = username
        alvo.usuario.email = email
        partes = nome.split()
        alvo.usuario.first_name = partes[0]
        alvo.usuario.last_name = " ".join(partes[1:])
        alvo.usuario.save()
        alvo.matricula = matricula
        alvo.save(update_fields=["matricula", "atualizado_em"])
        MatriculaAutorizada.objects.filter(matricula=antiga_matricula).update(matricula=matricula, nome=nome)

        messages.success(request, "Usuário atualizado com sucesso.")
        return redirect("usuarios_unidade")

    return render(request, "gestao/editar_usuario.html", {"perfil": _acesso(request.user), "acesso": alvo, "usuario": alvo.usuario, "perfil_usuario": getattr(alvo.usuario, "perfil_siev", None)})


@login_required
def usuarios_unidade_novo_senha(request, id):
    if not pode_administrar_usuarios(request.user):
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")
    alvo = get_object_or_404(AcessoInstitucional, id=id)
    if not _pode_ver_alvo(request.user, alvo):
        messages.error(request, "Você não possui acesso a este usuário.")
        return redirect("usuarios_unidade")

    if request.method == "POST":
        senha = request.POST.get("senha", "")
        confirmacao = request.POST.get("senha_confirmacao", "")
        if len(senha) < 6:
            messages.error(request, "A senha deve possuir pelo menos 6 caracteres.")
            return redirect("trocar_senha_usuario", id=id)
        if senha != confirmacao:
            messages.error(request, "As senhas não conferem.")
            return redirect("trocar_senha_usuario", id=id)
        alvo.usuario.set_password(senha)
        alvo.usuario.save(update_fields=["password"])
        alvo.primeiro_acesso = False
        alvo.save(update_fields=["primeiro_acesso", "atualizado_em"])
        messages.success(request, "Senha alterada com sucesso.")
        return redirect("usuarios_unidade")

    return render(request, "gestao/trocar_senha.html", {"perfil": _acesso(request.user), "perfil_usuario": alvo})


@login_required
def usuarios_unidade_novo_desativar(request, id):
    if not pode_administrar_usuarios(request.user):
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")
    alvo = get_object_or_404(AcessoInstitucional, id=id)
    if alvo.usuario_id == request.user.id:
        messages.error(request, "Você não pode desativar seu próprio usuário.")
        return redirect("usuarios_unidade")
    if not _pode_ver_alvo(request.user, alvo):
        messages.error(request, "Você não possui acesso a este usuário.")
        return redirect("usuarios_unidade")
    alvo.ativo = False
    alvo.save(update_fields=["ativo", "atualizado_em"])
    alvo.usuario.is_active = False
    alvo.usuario.save(update_fields=["is_active"])
    PerfilUsuario.objects.filter(usuario_id=alvo.usuario_id).update(ativo=False)
    MatriculaAutorizada.objects.filter(matricula=alvo.matricula).update(ativo=False)
    messages.success(request, "Usuário desativado com sucesso.")
    return redirect("usuarios_unidade")


@login_required
def usuarios_unidade_novo_excluir(request, id):
    if not pode_administrar_usuarios(request.user):
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")
    alvo = get_object_or_404(AcessoInstitucional, id=id)
    if alvo.usuario_id == request.user.id:
        messages.error(request, "Você não pode excluir seu próprio usuário.")
        return redirect("usuarios_unidade")
    if not _pode_ver_alvo(request.user, alvo):
        messages.error(request, "Você não possui acesso a este usuário.")
        return redirect("usuarios_unidade")
    if request.method != "POST":
        messages.error(request, "A exclusão deve ser confirmada pelo formulário.")
        return redirect("usuarios_unidade")
    matricula = alvo.matricula
    MatriculaAutorizada.objects.filter(matricula=matricula).delete()
    alvo.usuario.delete()
    messages.success(request, "Usuário excluído com sucesso.")
    return redirect("usuarios_unidade")
