from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import render, redirect

from apps.solicitacoes.models import PerfilUsuario
from apps.solicitacoes.models_acesso import AcessoInstitucional
from apps.solicitacoes.views.administracao_sistema import _enviar_senha_inicial


class OperadorForm(forms.Form):
    matricula = forms.CharField(max_length=30, label="Matrícula")
    nome = forms.CharField(max_length=150, label="Nome completo")
    cpf = forms.CharField(max_length=14, label="CPF")
    telefone = forms.CharField(max_length=25, label="Telefone")
    email = forms.EmailField(label="E-mail")

    def clean_matricula(self):
        valor = self.cleaned_data["matricula"].strip()
        if AcessoInstitucional.objects.filter(matricula__iexact=valor).exists():
            raise forms.ValidationError("Esta matrícula já está cadastrada.")
        return valor

    def clean_cpf(self):
        valor = self.cleaned_data["cpf"].strip()
        if AcessoInstitucional.objects.filter(cpf=valor).exists():
            raise forms.ValidationError("Este CPF já está cadastrado.")
        return valor


def _eh_membro_unidade(request):
    acesso = getattr(request.user, "acesso_institucional", None)
    return bool(
        request.user.is_authenticated
        and request.user.is_active
        and acesso
        and acesso.ativo
        and acesso.perfil == "UNIDADE"
        and acesso.funcao == "MEMBRO"
        and acesso.unidade_id
    )


@login_required
def administracao_unidade_membro(request):
    if not _eh_membro_unidade(request):
        messages.error(request, "Somente membros de Unidade podem cadastrar operadores nesta tela.")
        return redirect("painel_gestao")

    acesso = request.user.acesso_institucional
    if request.method == "POST":
        form = OperadorForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            senha = data["matricula"]
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=data["matricula"],
                        email=data["email"],
                        password=senha,
                        first_name=data["nome"],
                        is_active=True,
                    )
                    AcessoInstitucional.objects.create(
                        usuario=user,
                        matricula=data["matricula"],
                        cpf=data["cpf"],
                        telefone=data["telefone"],
                        perfil="OPERADOR",
                        funcao="MEMBRO",
                        cpr_id=acesso.unidade.cpr_id,
                        unidade_id=acesso.unidade_id,
                        primeiro_acesso=True,
                        ativo=True,
                    )
                    PerfilUsuario.objects.update_or_create(
                        usuario=user,
                        defaults={
                            "perfil": "OPERADOR",
                            "cpr_id": acesso.unidade.cpr_id,
                            "unidade_id": acesso.unidade_id,
                            "ativo": True,
                        },
                    )
                    _enviar_senha_inicial(user, senha)
            except Exception:
                if "user" in locals() and user.pk:
                    user.delete()
                form.add_error(None, "Não foi possível concluir o cadastro ou enviar a senha ao e-mail informado.")
            else:
                messages.success(request, "Operador cadastrado com sucesso. A senha inicial foi enviada por e-mail.")
                return redirect("administracao_unidade_membro")
    else:
        form = OperadorForm()

    operadores = (
        AcessoInstitucional.objects
        .filter(perfil="OPERADOR", unidade_id=acesso.unidade_id)
        .select_related("usuario")
        .order_by("usuario__first_name", "matricula")
    )
    return render(request, "administracao_sistema/operador_membro.html", {
        "form": form,
        "acesso": acesso,
        "operadores": operadores,
    })
