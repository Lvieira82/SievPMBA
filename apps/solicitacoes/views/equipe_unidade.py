from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.shortcuts import redirect, render

from apps.solicitacoes.models import MatriculaAutorizada, PerfilUsuario


GROUP_MEMBRO = "SIEV_MEMBRO"
GROUP_OPERADOR = "SIEV_OPERADOR"


class EquipeUnidadeForm(forms.Form):
    nome = forms.CharField(max_length=150, label="Nome completo")
    matricula = forms.CharField(max_length=20, label="Matrícula")
    posto = forms.CharField(max_length=30, required=False, label="Posto / Graduação")
    username = forms.CharField(max_length=150, label="Usuário de acesso")
    email = forms.EmailField(required=False, label="E-mail")
    senha = forms.CharField(min_length=8, widget=forms.PasswordInput, label="Senha")
    confirmar_senha = forms.CharField(widget=forms.PasswordInput, label="Confirmar senha")
    funcao = forms.ChoiceField(
        choices=[
            (GROUP_MEMBRO, "Membro operacional — gera OPOs e mapas"),
            (GROUP_OPERADOR, "Operador — consulta e cumpre eventos/OPOs"),
        ],
        label="Função operacional",
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Este usuário já existe.")
        return username

    def clean_matricula(self):
        matricula = self.cleaned_data["matricula"].strip()
        if MatriculaAutorizada.objects.filter(matricula=matricula, ativo=True).exists():
            raise forms.ValidationError("Esta matrícula já está cadastrada.")
        return matricula

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("senha") and cleaned.get("senha") != cleaned.get("confirmar_senha"):
            raise forms.ValidationError("As senhas não coincidem.")
        return cleaned


def _gestor_unidade(request):
    perfil = getattr(request.user, "perfil_siev", None)
    if not perfil or not perfil.ativo or perfil.perfil != "UNIDADE" or perfil.unidade_id is None:
        return None
    if request.user.groups.filter(name__in=[GROUP_MEMBRO, GROUP_OPERADOR]).exists():
        return None
    return perfil


def _grupo_funcao(usuario):
    if usuario.groups.filter(name=GROUP_MEMBRO).exists():
        return "Membro operacional"
    if usuario.groups.filter(name=GROUP_OPERADOR).exists():
        return "Operador"
    return "Gestor de Unidade"


@login_required
def equipe_unidade(request):
    perfil = _gestor_unidade(request)
    if not perfil:
        messages.error(request, "Somente o Gestor de Unidade pode administrar o efetivo da unidade.")
        return redirect("painel_gestao")

    usuarios = (
        PerfilUsuario.objects
        .filter(unidade_id=perfil.unidade_id, ativo=True)
        .select_related("usuario", "unidade")
        .prefetch_related("usuario__groups")
        .order_by("usuario__first_name", "usuario__username")
    )

    return render(
        request,
        "gestao/equipe_unidade.html",
        {"usuarios": usuarios, "perfil": perfil, "unidade": perfil.unidade},
    )


@login_required
def cadastrar_equipe_unidade(request):
    perfil = _gestor_unidade(request)
    if not perfil:
        messages.error(request, "Somente o Gestor de Unidade pode cadastrar membros e operadores.")
        return redirect("painel_gestao")

    if request.method == "POST":
        form = EquipeUnidadeForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=dados["username"],
                        email=dados["email"],
                        password=dados["senha"],
                        first_name=dados["nome"],
                        is_active=True,
                    )

                    PerfilUsuario.objects.create(
                        usuario=user,
                        perfil="UNIDADE",
                        unidade=perfil.unidade,
                        cpr=perfil.unidade.cpr,
                        ativo=True,
                    )

                    grupo, _ = Group.objects.get_or_create(name=dados["funcao"])
                    user.groups.add(grupo)

                    MatriculaAutorizada.objects.create(
                        matricula=dados["matricula"],
                        nome=dados["nome"],
                        posto=dados["posto"],
                        unidade=perfil.unidade,
                        ativo=True,
                    )

                messages.success(request, "Membro/operador cadastrado com sucesso.")
                return redirect("equipe_unidade")
            except Exception as erro:
                print("ERRO AO CADASTRAR EQUIPE:", repr(erro))
                form.add_error(None, "Não foi possível cadastrar o usuário.")
    else:
        form = EquipeUnidadeForm()

    return render(
        request,
        "gestao/cadastrar_equipe_unidade.html",
        {"form": form, "unidade": perfil.unidade},
    )