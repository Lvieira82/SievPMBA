from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from apps.solicitacoes.models import CPR, PerfilUsuario, Unidade


class UsuarioSistemaForm(forms.Form):
    nome = forms.CharField(max_length=150, label="Nome completo")
    username = forms.CharField(max_length=150, label="Usuário")
    email = forms.EmailField(required=False, label="E-mail")
    perfil = forms.ChoiceField(choices=PerfilUsuario.PERFIS, label="Nível de acesso")
    cpr = forms.ModelChoiceField(queryset=CPR.objects.none(), required=False, label="CPR")
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.none(), required=False, label="Unidade")
    ativo = forms.BooleanField(required=False, initial=True, label="Usuário ativo")

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.fields["cpr"].queryset = CPR.objects.filter(ativo=True).order_by("sigla")
        self.fields["unidade"].queryset = Unidade.objects.filter(ativo=True).select_related("cpr").order_by("nome")
        if instance:
            perfil = getattr(instance, "perfil_siev", None)
            self.initial.update({
                "nome": instance.get_full_name(),
                "username": instance.username,
                "email": instance.email,
                "perfil": perfil.perfil if perfil else "UNIDADE",
                "cpr": perfil.cpr_id if perfil else None,
                "unidade": perfil.unidade_id if perfil else None,
                "ativo": perfil.ativo if perfil else instance.is_active,
            })

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username=username)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Este usuário já existe.")
        return username

    def clean(self):
        cleaned = super().clean()
        perfil = cleaned.get("perfil")
        if perfil == "CPR" and not cleaned.get("cpr"):
            self.add_error("cpr", "Selecione o CPR do usuário.")
        if perfil == "UNIDADE" and not cleaned.get("unidade"):
            self.add_error("unidade", "Selecione a unidade do usuário.")
        if perfil == "COPPM":
            cleaned["cpr"] = None
            cleaned["unidade"] = None
        return cleaned


class SenhaForm(forms.Form):
    senha = forms.CharField(min_length=8, widget=forms.PasswordInput, label="Nova senha")
    confirmar = forms.CharField(widget=forms.PasswordInput, label="Confirmar nova senha")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("senha") != cleaned.get("confirmar"):
            raise forms.ValidationError("As senhas não coincidem.")
        return cleaned


def _somente_desenvolvedor(request):
    return request.user.is_authenticated and request.user.is_superuser


@login_required
def administracao_sistema(request):
    if not _somente_desenvolvedor(request):
        messages.error(request, "Somente o usuário desenvolvedor pode acessar a administração do sistema.")
        return redirect("painel_gestao")

    perfis = PerfilUsuario.objects.select_related("usuario", "cpr", "unidade").order_by("usuario__first_name", "usuario__username")
    return render(request, "administracao_sistema/index.html", {"perfis": perfis, "superusuarios": User.objects.filter(is_superuser=True).count()})


@login_required
def usuario_novo(request):
    if not _somente_desenvolvedor(request):
        messages.error(request, "Acesso restrito ao desenvolvedor.")
        return redirect("painel_gestao")

    if request.method == "POST":
        form = UsuarioSistemaForm(request.POST)
        senha = request.POST.get("senha", "")
        confirmar = request.POST.get("confirmar", "")
        if not senha or len(senha) < 8 or senha != confirmar:
            form.add_error(None, "Informe uma senha de pelo menos 8 caracteres e confirme corretamente.")
        elif form.is_valid():
            data = form.cleaned_data
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=senha,
                first_name=data["nome"],
                is_active=data["ativo"],
            )
            PerfilUsuario.objects.create(
                usuario=user,
                perfil=data["perfil"],
                cpr=data["cpr"],
                unidade=data["unidade"],
                ativo=data["ativo"],
            )
            messages.success(request, "Usuário criado e nível de acesso liberado.")
            return redirect("administracao_sistema")
    else:
        form = UsuarioSistemaForm()

    return render(request, "administracao_sistema/form.html", {"form": form, "novo": True})


@login_required
def usuario_editar(request, id):
    if not _somente_desenvolvedor(request):
        messages.error(request, "Acesso restrito ao desenvolvedor.")
        return redirect("painel_gestao")

    user = get_object_or_404(User, pk=id)
    if request.method == "POST":
        form = UsuarioSistemaForm(request.POST, instance=user)
        if form.is_valid():
            data = form.cleaned_data
            user.first_name = data["nome"]
            user.email = data["email"]
            user.username = data["username"]
            user.is_active = data["ativo"]
            user.save()
            perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
            perfil.perfil = data["perfil"]
            perfil.cpr = data["cpr"]
            perfil.unidade = data["unidade"]
            perfil.ativo = data["ativo"]
            perfil.save()
            messages.success(request, "Usuário e nível de acesso atualizados.")
            return redirect("administracao_sistema")
    else:
        form = UsuarioSistemaForm(instance=user)

    return render(request, "administracao_sistema/form.html", {"form": form, "novo": False, "usuario": user})


@login_required
def usuario_senha(request, id):
    if not _somente_desenvolvedor(request):
        messages.error(request, "Acesso restrito ao desenvolvedor.")
        return redirect("painel_gestao")

    user = get_object_or_404(User, pk=id)
    if request.method == "POST":
        form = SenhaForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data["senha"])
            user.save(update_fields=["password"])
            messages.success(request, "Senha alterada com sucesso.")
            return redirect("administracao_sistema")
    else:
        form = SenhaForm()
    return render(request, "administracao_sistema/senha.html", {"form": form, "usuario": user})


@login_required
def usuario_desativar(request, id):
    if not _somente_desenvolvedor(request):
        messages.error(request, "Acesso restrito ao desenvolvedor.")
        return redirect("painel_gestao")
    user = get_object_or_404(User, pk=id)
    if user.is_superuser:
        messages.error(request, "O desenvolvedor principal não pode ser desativado por esta tela.")
        return redirect("administracao_sistema")
    user.is_active = False
    user.save(update_fields=["is_active"])
    perfil = getattr(user, "perfil_siev", None)
    if perfil:
        perfil.ativo = False
        perfil.save(update_fields=["ativo"])
    messages.success(request, "Usuário desativado.")
    return redirect("administracao_sistema")


@login_required
def usuario_excluir(request, id):
    if not _somente_desenvolvedor(request):
        messages.error(request, "Acesso restrito ao desenvolvedor.")
        return redirect("painel_gestao")

    user = get_object_or_404(User, pk=id)

    if user.is_superuser:
        messages.error(request, "O usuário desenvolvedor não pode ser excluído por esta tela.")
        return redirect("administracao_sistema")

    if user.pk == request.user.pk:
        messages.error(request, "Você não pode excluir o próprio usuário.")
        return redirect("administracao_sistema")

    if request.method != "POST":
        messages.error(request, "A exclusão deve ser confirmada pelo botão Excluir.")
        return redirect("administracao_sistema")

    nome = user.get_full_name() or user.username
    try:
        with transaction.atomic():
            user.delete()
    except ProtectedError:
        messages.error(
            request,
            "Este usuário possui registros que dependem dele (por exemplo, transferências) e não pode ser excluído. Desative-o em vez disso.",
        )
        return redirect("administracao_sistema")

    messages.success(request, f"Usuário {nome} excluído com sucesso.")
    return redirect("administracao_sistema")
