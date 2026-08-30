import secrets
import string

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import CPR, PerfilUsuario, Unidade
from apps.solicitacoes.models_acesso import AcessoInstitucional


AMBITOS = [
    ("COPPM", "COPPM"),
    ("CPR", "CPR"),
    ("UNIDADE", "Unidade"),
]
FUNCOES = [
    ("GESTOR", "Gestor"),
    ("MEMBRO", "Membro"),
]
PERFIS_ACESSO = [
    ("MEMBRO", "Membro"),
    ("OPERADOR", "Operador"),
]


class UsuarioSistemaForm(forms.Form):
    matricula = forms.CharField(max_length=30, label="Matrícula")
    nome = forms.CharField(max_length=150, label="Nome completo")
    cpf = forms.CharField(max_length=14, required=False, label="CPF")
    telefone = forms.CharField(max_length=25, required=False, label="Telefone")
    email = forms.EmailField(label="E-mail de validação")
    perfil = forms.ChoiceField(choices=AMBITOS, label="Âmbito")
    perfil_acesso = forms.ChoiceField(choices=PERFIS_ACESSO, label="Perfil")
    funcao = forms.ChoiceField(choices=FUNCOES, label="Função")
    cpr = forms.ModelChoiceField(
        queryset=CPR.objects.none(), required=False, label="CPR"
    )
    unidade = forms.ModelChoiceField(
        queryset=Unidade.objects.none(), required=False, label="Unidade"
    )
    ativo = forms.BooleanField(required=False, initial=True, label="Usuário ativo")

    def __init__(self, *args, instance=None, scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.scope = scope

        self.fields["cpr"].queryset = CPR.objects.filter(ativo=True).order_by("sigla")
        self.fields["unidade"].queryset = (
            Unidade.objects.filter(ativo=True)
            .select_related("cpr")
            .order_by("nome")
        )

        if scope and not scope["desenvolvedor"]:
            # Gestores/membros institucionais não criam outro gestor.
            self.fields["funcao"].initial = "MEMBRO"
            self.fields["funcao"].widget = forms.HiddenInput()
            self.fields["perfil_acesso"].choices = PERFIS_ACESSO
            self.fields["perfil_acesso"].initial = "MEMBRO"

            if scope["perfil"] == "COPPM":
                # COPPM pode escolher qualquer CPR ou Unidade.
                self.fields["perfil"].initial = "CPR"
                self.fields["cpr"].queryset = CPR.objects.filter(ativo=True).order_by("sigla")
                self.fields["unidade"].queryset = (
                    Unidade.objects.filter(ativo=True)
                    .select_related("cpr")
                    .order_by("cpr__sigla", "nome")
                )

            elif scope["perfil"] == "CPR":
                self.fields["perfil"].initial = "CPR"
                self.fields["perfil"].disabled = True
                self.fields["cpr"].queryset = CPR.objects.filter(pk=scope["cpr"].pk)
                self.fields["cpr"].initial = scope["cpr"].pk
                self.fields["cpr"].disabled = True
                self.fields["unidade"].queryset = (
                    Unidade.objects.filter(cpr=scope["cpr"], ativo=True)
                    .select_related("cpr")
                    .order_by("nome")
                )

            elif scope["perfil"] == "UNIDADE":
                self.fields["perfil"].initial = "UNIDADE"
                self.fields["perfil"].disabled = True
                self.fields["cpr"].queryset = CPR.objects.filter(pk=scope["cpr"].pk)
                self.fields["cpr"].initial = scope["cpr"].pk
                self.fields["cpr"].disabled = True
                self.fields["unidade"].queryset = Unidade.objects.filter(
                    pk=scope["unidade"].pk
                )
                self.fields["unidade"].initial = scope["unidade"].pk
                self.fields["unidade"].disabled = True

        if instance:
            acesso = getattr(instance, "acesso_institucional", None)
            if acesso:
                if acesso.perfil == "OPERADOR":
                    tipo = "OPERADOR"
                    ambito = "UNIDADE" if acesso.unidade_id else "CPR"
                else:
                    tipo = "MEMBRO"
                    ambito = acesso.perfil

                self.initial.update({
                    "matricula": acesso.matricula,
                    "nome": instance.get_full_name(),
                    "cpf": acesso.cpf or "",
                    "telefone": acesso.telefone or "",
                    "email": instance.email,
                    "perfil": ambito,
                    "perfil_acesso": tipo,
                    "funcao": acesso.funcao,
                    "cpr": acesso.cpr_id,
                    "unidade": acesso.unidade_id,
                    "ativo": acesso.ativo and instance.is_active,
                })

                # Apenas o superusuário pode editar a função institucional.
                if scope and not scope["desenvolvedor"]:
                    self.fields["funcao"].initial = "MEMBRO"
                    self.fields["funcao"].widget = forms.HiddenInput()

    def clean_matricula(self):
        valor = self.cleaned_data["matricula"].strip()
        qs = AcessoInstitucional.objects.filter(matricula__iexact=valor)
        if self.instance:
            qs = qs.exclude(usuario=self.instance)
        if qs.exists() or User.objects.filter(
            username=valor
        ).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise forms.ValidationError("Esta matrícula já está cadastrada.")
        return valor

    def clean_cpf(self):
        valor = self.cleaned_data["cpf"].strip()
        if not valor:
            return ""
        qs = AcessoInstitucional.objects.filter(cpf=valor)
        if self.instance:
            qs = qs.exclude(usuario=self.instance)
        if qs.exists():
            raise forms.ValidationError("Este CPF já está cadastrado.")
        return valor

    def clean(self):
        cleaned = super().clean()
        ambito = cleaned.get("perfil")
        perfil_acesso = cleaned.get("perfil_acesso")
        funcao = cleaned.get("funcao")
        cpr = cleaned.get("cpr")
        unidade = cleaned.get("unidade")

        if self.scope and not self.scope["desenvolvedor"]:
            # Nunca aceitar pelo POST uma função de gestor enviada manualmente.
            cleaned["funcao"] = "MEMBRO"
            funcao = "MEMBRO"

            if self.scope["perfil"] == "COPPM":
                if ambito not in {"COPPM", "CPR", "UNIDADE"}:
                    self.add_error("perfil", "Selecione o âmbito institucional.")
                if ambito == "COPPM":
                    cleaned["cpr"] = None
                    cleaned["unidade"] = None
                elif ambito == "CPR":
                    if not cpr:
                        self.add_error("cpr", "Selecione o CPR.")
                    cleaned["unidade"] = None
                elif ambito == "UNIDADE":
                    if not cpr:
                        self.add_error("cpr", "Selecione o CPR.")
                    if not unidade:
                        self.add_error("unidade", "Selecione a unidade.")
                    if cpr and unidade and unidade.cpr_id != cpr.id:
                        self.add_error(
                            "unidade",
                            "A unidade selecionada não pertence ao CPR informado.",
                        )

            elif self.scope["perfil"] == "CPR":
                cleaned["perfil"] = "CPR"
                cleaned["cpr"] = self.scope["cpr"]
                if perfil_acesso == "OPERADOR":
                    if not unidade:
                        self.add_error("unidade", "Selecione a unidade do operador.")
                    elif unidade.cpr_id != self.scope["cpr"].id:
                        self.add_error(
                            "unidade", "A unidade deve pertencer ao seu CPR."
                        )
                else:
                    cleaned["unidade"] = None

            elif self.scope["perfil"] == "UNIDADE":
                cleaned["perfil"] = "UNIDADE"
                cleaned["cpr"] = self.scope["cpr"]
                cleaned["unidade"] = self.scope["unidade"]

            if perfil_acesso not in {"MEMBRO", "OPERADOR"}:
                self.add_error("perfil_acesso", "Selecione Membro ou Operador.")

            return cleaned

        # Superusuário: cria/edita gestores institucionais.
        if funcao != "GESTOR":
            self.add_error("funcao", "O administrador deve cadastrar gestores institucionais.")
        if perfil_acesso != "MEMBRO":
            self.add_error("perfil_acesso", "Gestor institucional deve possuir perfil Membro.")

        if ambito == "COPPM":
            cleaned["cpr"] = None
            cleaned["unidade"] = None
        elif ambito == "CPR":
            if not cpr:
                self.add_error("cpr", "Selecione o CPR do gestor.")
            cleaned["unidade"] = None
        elif ambito == "UNIDADE":
            if not cpr:
                self.add_error("cpr", "Selecione o CPR da unidade.")
            if not unidade:
                self.add_error("unidade", "Selecione a unidade do gestor.")
            if cpr and unidade and unidade.cpr_id != cpr.id:
                self.add_error(
                    "unidade",
                    "A unidade selecionada não pertence ao CPR informado.",
                )
        else:
            self.add_error("perfil", "Selecione o âmbito institucional.")

        return cleaned


def _escopo(request):
    if request.user.is_superuser:
        return {
            "desenvolvedor": True,
            "perfil": None,
            "cpr": None,
            "unidade": None,
            "funcao": "GESTOR",
        }

    acesso = getattr(request.user, "acesso_institucional", None)
    if not acesso or not acesso.ativo or not request.user.is_active:
        return None

    if acesso.perfil == "CPR" and acesso.cpr:
        return {
            "desenvolvedor": False,
            "perfil": "CPR",
            "cpr": acesso.cpr,
            "unidade": None,
            "funcao": acesso.funcao,
        }

    if acesso.perfil == "UNIDADE" and acesso.unidade:
        return {
            "desenvolvedor": False,
            "perfil": "UNIDADE",
            "cpr": acesso.unidade.cpr,
            "unidade": acesso.unidade,
            "funcao": acesso.funcao,
        }

    if acesso.perfil == "COPPM":
        return {
            "desenvolvedor": False,
            "perfil": "COPPM",
            "cpr": None,
            "unidade": None,
            "funcao": acesso.funcao,
        }

    return None


def _pode_gerenciar(scope, acesso):
    if not scope or not acesso:
        return False

    if scope["desenvolvedor"]:
        return not acesso.usuario.is_superuser

    # Todos os perfis institucionais podem administrar seus usuários.
    # Gestores não podem administrar outro gestor; somente membros/operadores.
    if acesso.funcao != "MEMBRO":
        return False

    if scope["perfil"] == "COPPM":
        return acesso.perfil in {"COPPM", "CPR", "UNIDADE", "OPERADOR"}

    if scope["perfil"] == "CPR":
        return acesso.cpr_id == scope["cpr"].id and acesso.perfil in {
            "CPR", "OPERADOR"
        }

    if scope["perfil"] == "UNIDADE":
        return acesso.unidade_id == scope["unidade"].id and acesso.perfil in {
            "UNIDADE", "OPERADOR"
        }

    return False


def _senha_inicial():
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(12)
    )


def _enviar_senha_inicial(user, senha):
    send_mail(
        "Seu acesso institucional ao SiEv",
        (
            f"Olá, {user.get_full_name()}.\n\n"
            "Seu acesso institucional ao SiEv foi criado.\n\n"
            f"Matrícula: {user.username}\n"
            f"Senha inicial: {senha}\n\n"
            "No primeiro acesso o sistema exigirá a troca desta senha.\n"
            "Nunca compartilhe sua senha."
        ),
        None,
        [user.email],
        fail_silently=False,
    )


def _sincronizar_perfil_compat(user, data):
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
    perfil.perfil = (
        data["perfil"] if data["perfil"] != "OPERADOR" else "UNIDADE"
    )
    perfil.cpr = data["cpr"]
    perfil.unidade = data["unidade"]
    perfil.ativo = data["ativo"]
    perfil.save()


def _perfil_modelo(data):
    if data["funcao"] == "GESTOR":
        return data["perfil"]
    return "OPERADOR" if data["perfil_acesso"] == "OPERADOR" else data["perfil"]


@login_required
def administracao_sistema(request):
    scope = _escopo(request)
    if not scope:
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")

    qs = AcessoInstitucional.objects.select_related("usuario", "cpr", "unidade")

    if not scope["desenvolvedor"]:
        if scope["perfil"] == "COPPM":
            qs = qs.filter(funcao="MEMBRO").exclude(perfil="COPPM")
        elif scope["perfil"] == "CPR":
            qs = qs.filter(
                funcao="MEMBRO",
                cpr=scope["cpr"],
                perfil__in=["CPR", "OPERADOR"],
            )
        elif scope["perfil"] == "UNIDADE":
            from django.db.models import Q
            qs = qs.filter(
                funcao="MEMBRO",
                Q(perfil="UNIDADE", unidade=scope["unidade"]) |
                Q(perfil="OPERADOR", unidade=scope["unidade"])
            )

    return render(
        request,
        "administracao_sistema/index.html",
        {
            "acessos": qs.order_by("usuario__first_name", "matricula"),
            "perfis": qs,
            "scope": scope,
        },
    )


@login_required
def usuario_novo(request):
    scope = _escopo(request)
    if not scope:
        messages.error(request, "Você não possui permissão para cadastrar usuários.")
        return redirect("painel_gestao")

    if request.method == "POST":
        form = UsuarioSistemaForm(request.POST, scope=scope)
        if form.is_valid():
            data = form.cleaned_data

            if not scope["desenvolvedor"]:
                data["funcao"] = "MEMBRO"
                if scope["perfil"] == "CPR":
                    data["perfil"] = "CPR"
                    data["cpr"] = scope["cpr"]
                elif scope["perfil"] == "UNIDADE":
                    data["perfil"] = "UNIDADE"
                    data["cpr"] = scope["cpr"]
                    data["unidade"] = scope["unidade"]

            data["perfil"] = _perfil_modelo(data)
            senha = _senha_inicial()

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=data["matricula"],
                        email=data["email"],
                        password=senha,
                        first_name=data["nome"],
                        is_active=data["ativo"],
                    )
                    AcessoInstitucional.objects.create(
                        usuario=user,
                        matricula=data["matricula"],
                        cpf=data["cpf"] or None,
                        telefone=data["telefone"],
                        perfil=data["perfil"],
                        funcao=data["funcao"],
                        cpr=data["cpr"],
                        unidade=data["unidade"],
                        primeiro_acesso=True,
                        ativo=data["ativo"],
                    )
                    _sincronizar_perfil_compat(user, data)
                    _enviar_senha_inicial(user, senha)
            except Exception:
                if "user" in locals() and user.pk:
                    user.delete()
                form.add_error(
                    None,
                    "Não foi possível concluir o cadastro ou enviar a senha para o e-mail informado.",
                )
            else:
                messages.success(
                    request,
                    "Usuário criado. A senha inicial foi enviada para o e-mail cadastrado.",
                )
                return redirect("administracao_sistema")
    else:
        form = UsuarioSistemaForm(scope=scope)

    return render(
        request,
        "administracao_sistema/form.html",
        {"form": form, "novo": True, "scope": scope},
    )


@login_required
def usuario_editar(request, id):
    scope = _escopo(request)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)

    if not scope or not _pode_gerenciar(scope, acesso):
        messages.error(request, "Você não pode alterar este cadastro.")
        return redirect("administracao_sistema")

    if request.method == "POST":
        form = UsuarioSistemaForm(request.POST, instance=user, scope=scope)
        if form.is_valid():
            data = form.cleaned_data

            if not scope["desenvolvedor"]:
                data["funcao"] = "MEMBRO"
                if scope["perfil"] == "CPR":
                    data["perfil"] = "CPR"
                    data["cpr"] = scope["cpr"]
                elif scope["perfil"] == "UNIDADE":
                    data["perfil"] = "UNIDADE"
                    data["cpr"] = scope["cpr"]
                    data["unidade"] = scope["unidade"]

            data["perfil"] = _perfil_modelo(data)

            user.username = data["matricula"]
            user.first_name = data["nome"]
            user.email = data["email"]
            user.is_active = data["ativo"]
            user.save(update_fields=["username", "first_name", "email", "is_active"])

            acesso.matricula = data["matricula"]
            acesso.cpf = data["cpf"] or None
            acesso.telefone = data["telefone"]
            acesso.perfil = data["perfil"]
            acesso.funcao = data["funcao"]
            acesso.cpr = data["cpr"]
            acesso.unidade = data["unidade"]
            acesso.ativo = data["ativo"]
            acesso.save()
            _sincronizar_perfil_compat(user, data)

            messages.success(request, "Cadastro atualizado.")
            return redirect("administracao_sistema")
    else:
        form = UsuarioSistemaForm(instance=user, scope=scope)

    return render(
        request,
        "administracao_sistema/form.html",
        {
            "form": form,
            "novo": False,
            "usuario": user,
            "scope": scope,
        },
    )


@login_required
def usuario_senha(request, id):
    scope = _escopo(request)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)

    if not scope or not _pode_gerenciar(scope, acesso):
        messages.error(request, "Você não pode alterar a senha deste usuário.")
        return redirect("administracao_sistema")

    if request.method == "POST":
        senha = _senha_inicial()
        user.set_password(senha)
        user.save(update_fields=["password"])
        acesso.primeiro_acesso = True
        acesso.save(update_fields=["primeiro_acesso", "atualizado_em"])

        try:
            _enviar_senha_inicial(user, senha)
            messages.success(
                request,
                "Nova senha provisória enviada para o e-mail do usuário.",
            )
        except Exception:
            messages.error(
                request,
                "A senha foi redefinida, mas não foi possível enviar o e-mail. Verifique o serviço de e-mail.",
            )

        return redirect("administracao_sistema")

    return render(
        request,
        "administracao_sistema/senha.html",
        {"usuario": user},
    )


@login_required
def usuario_desativar(request, id):
    scope = _escopo(request)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)

    if not scope or not _pode_gerenciar(scope, acesso):
        messages.error(request, "Você não pode alterar este cadastro.")
        return redirect("administracao_sistema")

    acesso.ativo = False
    acesso.save(update_fields=["ativo", "atualizado_em"])
    user.is_active = False
    user.save(update_fields=["is_active"])

    messages.success(request, "Usuário desativado.")
    return redirect("administracao_sistema")


@login_required
def usuario_excluir(request, id):
    scope = _escopo(request)
    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)

    if not scope or not _pode_gerenciar(scope, acesso):
        messages.error(request, "Você não pode excluir este usuário.")
        return redirect("administracao_sistema")

    if request.method != "POST":
        messages.error(request, "A exclusão deve ser confirmada pelo formulário.")
        return redirect("administracao_sistema")

    if user.is_superuser:
        messages.error(request, "O superusuário não pode ser excluído por esta tela.")
        return redirect("administracao_sistema")

    nome = user.get_full_name() or user.username
    user.delete()
    messages.success(request, f"Usuário {nome} excluído definitivamente.")
    return redirect("administracao_sistema")
