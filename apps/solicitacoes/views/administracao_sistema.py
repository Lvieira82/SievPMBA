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


PERFIS = [
    ("COPPM", "COPPM"),
    ("CPR", "CPR"),
    ("UNIDADE", "Unidade"),
    ("OPERADOR", "Operador"),
]
FUNCOES = [
    ("GESTOR", "Gestor"),
    ("MEMBRO", "Membro"),
]


class UsuarioSistemaForm(forms.Form):
    matricula = forms.CharField(max_length=30, label="Matrícula")
    nome = forms.CharField(max_length=150, label="Nome completo")
    cpf = forms.CharField(max_length=14, label="CPF")
    telefone = forms.CharField(max_length=25, label="Telefone")
    email = forms.EmailField(label="E-mail")
    perfil = forms.ChoiceField(choices=PERFIS, label="Âmbito")
    funcao = forms.ChoiceField(choices=FUNCOES, label="Função")
    cpr = forms.ModelChoiceField(queryset=CPR.objects.none(), required=False, label="CPR")
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.none(), required=False, label="Unidade")
    ativo = forms.BooleanField(required=False, initial=True, label="Usuário ativo")

    def __init__(self, *args, instance=None, scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.scope = scope

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({"class": "form-check-input"})
            else:
                field.widget.attrs.update({"class": "form-control"})

        for name in ("perfil", "funcao", "cpr", "unidade"):
            self.fields[name].widget.attrs["class"] = "form-select"

        self.fields["cpr"].queryset = CPR.objects.filter(ativo=True).order_by("sigla")
        self.fields["unidade"].queryset = (
            Unidade.objects.filter(ativo=True).select_related("cpr").order_by("nome")
        )

        if scope and not scope["desenvolvedor"]:
            if scope["perfil"] == "CPR":
                self.fields["perfil"].choices = [("CPR", "CPR")]
                self.fields["perfil"].initial = "CPR"
                self.fields["perfil"].disabled = True
                self.fields["funcao"].initial = "MEMBRO"
                self.fields["funcao"].disabled = True
                self.fields["cpr"].queryset = CPR.objects.filter(pk=scope["cpr"].pk)
                self.fields["cpr"].initial = scope["cpr"].pk
                self.fields["cpr"].disabled = True
                self.fields["unidade"].queryset = (
                    Unidade.objects.filter(cpr=scope["cpr"], ativo=True)
                    .select_related("cpr").order_by("nome")
                )

            elif scope["perfil"] == "UNIDADE":
                # O Gestor de Unidade pode cadastrar membro da unidade ou Operador.
                self.fields["perfil"].choices = [
                    ("UNIDADE", "Membro de Unidade"),
                    ("OPERADOR", "Operador"),
                ]
                self.fields["perfil"].initial = "UNIDADE"
                self.fields["cpr"].queryset = CPR.objects.filter(pk=scope["unidade"].cpr_id)
                self.fields["cpr"].initial = scope["unidade"].cpr_id
                self.fields["cpr"].disabled = True
                self.fields["unidade"].queryset = Unidade.objects.filter(pk=scope["unidade"].pk)
                self.fields["unidade"].initial = scope["unidade"].pk
                self.fields["unidade"].disabled = True
                self.fields["funcao"].initial = "MEMBRO"
                self.fields["funcao"].disabled = True

            elif scope["perfil"] == "COPPM":
                self.fields["perfil"].choices = [("COPPM", "COPPM")]
                self.fields["perfil"].initial = "COPPM"
                self.fields["perfil"].disabled = True
                self.fields["funcao"].initial = "MEMBRO"
                self.fields["funcao"].disabled = True

        if instance:
            acesso = getattr(instance, "acesso_institucional", None)
            if acesso:
                self.initial.update({
                    "matricula": acesso.matricula,
                    "nome": instance.get_full_name(),
                    "cpf": acesso.cpf,
                    "telefone": acesso.telefone,
                    "email": instance.email,
                    "perfil": acesso.perfil,
                    "funcao": acesso.funcao,
                    "cpr": acesso.cpr_id,
                    "unidade": acesso.unidade_id,
                    "ativo": acesso.ativo and instance.is_active,
                })
                if scope and not scope["desenvolvedor"]:
                    self.fields["perfil"].disabled = True

    def clean_matricula(self):
        valor = self.cleaned_data["matricula"].strip()
        qs = AcessoInstitucional.objects.filter(matricula__iexact=valor)
        if self.instance:
            qs = qs.exclude(usuario=self.instance)
        if qs.exists():
            raise forms.ValidationError("Esta matrícula já está cadastrada.")
        return valor

    def clean_cpf(self):
        valor = self.cleaned_data["cpf"].strip()
        qs = AcessoInstitucional.objects.filter(cpf=valor)
        if self.instance:
            qs = qs.exclude(usuario=self.instance)
        if qs.exists():
            raise forms.ValidationError("Este CPF já está cadastrado.")
        return valor

    def clean(self):
        cleaned = super().clean()
        perfil = cleaned.get("perfil")
        funcao = cleaned.get("funcao")
        cpr = cleaned.get("cpr")
        unidade = cleaned.get("unidade")

        if perfil in ("UNIDADE", "OPERADOR") and not unidade:
            self.add_error("unidade", "Selecione a unidade.")

        if perfil == "CPR" and not cpr:
            self.add_error("cpr", "Selecione o CPR.")

        if cpr and unidade and unidade.cpr_id != cpr.id:
            self.add_error("unidade", "A unidade selecionada não pertence ao CPR informado.")

        if perfil in ("COPPM", "OPERADOR"):
            if perfil == "COPPM":
                cleaned["cpr"] = None
                cleaned["unidade"] = None
            elif unidade:
                cleaned["cpr"] = unidade.cpr

        if self.scope and not self.scope["desenvolvedor"]:
            if funcao != "MEMBRO":
                self.add_error("funcao", "Somente membros podem ser cadastrados por gestores.")

            if self.scope["perfil"] == "CPR":
                if perfil != "CPR":
                    self.add_error("perfil", "O Gestor CPR só pode cadastrar membros do CPR.")
                if unidade and unidade.cpr_id != self.scope["cpr"].id:
                    self.add_error("unidade", "A unidade não pertence ao seu CPR.")

            elif self.scope["perfil"] == "UNIDADE":
                if perfil not in ("UNIDADE", "OPERADOR"):
                    self.add_error("perfil", "Perfil não permitido para esta unidade.")
                if unidade and unidade.id != self.scope["unidade"].id:
                    self.add_error("unidade", "Você só pode cadastrar membros da sua unidade.")

            elif self.scope["perfil"] == "COPPM" and perfil != "COPPM":
                self.add_error("perfil", "O Gestor COPPM só pode cadastrar membros da COPPM.")

        return cleaned


def _escopo(request):
    if request.user.is_superuser:
        return {"desenvolvedor": True, "perfil": None, "cpr": None, "unidade": None}

    acesso = getattr(request.user, "acesso_institucional", None)
    if not acesso or not acesso.ativo or acesso.funcao != "GESTOR":
        return None

    if acesso.perfil == "CPR" and acesso.cpr:
        return {"desenvolvedor": False, "perfil": "CPR", "cpr": acesso.cpr, "unidade": None}
    if acesso.perfil == "UNIDADE" and acesso.unidade:
        return {"desenvolvedor": False, "perfil": "UNIDADE", "cpr": acesso.unidade.cpr, "unidade": acesso.unidade}
    if acesso.perfil == "COPPM":
        return {"desenvolvedor": False, "perfil": "COPPM", "cpr": None, "unidade": None}
    return None


def _pode_gerenciar(scope, acesso):
    if not scope or not acesso:
        return False
    if scope["desenvolvedor"]:
        return True
    if acesso.funcao != "MEMBRO":
        return False
    if scope["perfil"] == "COPPM":
        return acesso.perfil == "COPPM"
    if scope["perfil"] == "CPR":
        return acesso.perfil == "CPR" and acesso.cpr_id == scope["cpr"].id
    if scope["perfil"] == "UNIDADE":
        return acesso.perfil in ("UNIDADE", "OPERADOR") and acesso.unidade_id == scope["unidade"].id
    return False


def _senha_inicial():
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(12))


def _enviar_senha_inicial(user, senha):
    send_mail(
        subject="Seu acesso institucional ao SiEv",
        message=(
            f"Olá, {user.get_full_name()}.\n\n"
            "Seu acesso institucional ao SiEv foi criado.\n\n"
            f"Matrícula: {user.username}\n"
            f"Senha inicial: {senha}\n\n"
            "No primeiro acesso o sistema exigirá a troca desta senha.\n"
            "Nunca compartilhe sua senha."
        ),
        from_email=None,
        recipient_list=[user.email],
        fail_silently=False,
    )


def _sincronizar_perfil_compat(user, data):
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
    perfil.perfil = data["perfil"]
    perfil.cpr = data["cpr"]
    perfil.unidade = data["unidade"]
    perfil.ativo = data["ativo"]
    perfil.save()


@login_required
def administracao_sistema(request):
    scope = _escopo(request)
    if not scope:
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")

    qs = AcessoInstitucional.objects.select_related("usuario", "cpr", "unidade")
    if not scope["desenvolvedor"]:
        if scope["perfil"] == "COPPM":
            qs = qs.filter(perfil="COPPM", funcao="MEMBRO")
        elif scope["perfil"] == "CPR":
            qs = qs.filter(perfil="CPR", funcao="MEMBRO", cpr=scope["cpr"])
        elif scope["perfil"] == "UNIDADE":
            from django.db.models import Q
            qs = qs.filter(
                Q(perfil="UNIDADE", funcao="MEMBRO", unidade=scope["unidade"]) |
                Q(perfil="OPERADOR", funcao="MEMBRO", unidade=scope["unidade"])
            )

    return render(request, "administracao_sistema/index.html", {
        "acessos": qs.order_by("usuario__first_name", "matricula"),
        "perfis": qs,
        "scope": scope,
    })


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
                    data["unidade"] = scope["unidade"]
                    data["cpr"] = scope["cpr"]
                    if data["perfil"] not in ("UNIDADE", "OPERADOR"):
                        data["perfil"] = "UNIDADE"
                elif scope["perfil"] == "COPPM":
                    data["perfil"] = "COPPM"
                    data["cpr"] = None
                    data["unidade"] = None

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
                        cpf=data["cpf"],
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
                form.add_error(None, "Não foi possível concluir o cadastro ou enviar a senha para o e-mail informado.")
            else:
                messages.success(request, "Usuário criado. A senha inicial foi enviada para o e-mail cadastrado.")
                return redirect("administracao_sistema")
    else:
        form = UsuarioSistemaForm(scope=scope)

    return render(request, "administracao_sistema/form.html", {"form": form, "novo": True, "scope": scope})


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
                data["perfil"] = acesso.perfil
                data["funcao"] = acesso.funcao
                data["cpr"] = acesso.cpr
                data["unidade"] = acesso.unidade
            user.first_name = data["nome"]
            user.email = data["email"]
            user.is_active = data["ativo"]
            user.save(update_fields=["first_name", "email", "is_active"])
            acesso.matricula = data["matricula"]
            acesso.cpf = data["cpf"]
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

    return render(request, "administracao_sistema/form.html", {"form": form, "novo": False, "usuario": user, "scope": scope})


@login_required
def usuario_senha(request, id):
    if not request.user.is_superuser:
        messages.error(request, "Gestores não podem alterar senhas. O usuário deve usar o primeiro acesso ou 'Esqueci minha senha'.")
        return redirect("administracao_sistema")

    user = get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)
    if not acesso:
        messages.error(request, "Este usuário não possui cadastro institucional.")
        return redirect("administracao_sistema")

    if request.method == "POST":
        senha = _senha_inicial()
        user.set_password(senha)
        user.save(update_fields=["password"])
        acesso.primeiro_acesso = True
        acesso.save(update_fields=["primeiro_acesso", "atualizado_em"])
        try:
            _enviar_senha_inicial(user, senha)
        except Exception:
            messages.error(request, "A senha foi redefinida, mas não foi possível enviar o e-mail. Verifique o serviço de e-mail.")
        else:
            messages.success(request, "Nova senha provisória enviada para o e-mail do usuário.")
        return redirect("administracao_sistema")

    return render(request, "administracao_sistema/senha.html", {"usuario": user})


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
