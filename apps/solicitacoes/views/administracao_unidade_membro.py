from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, render, redirect

from apps.solicitacoes.models import PerfilUsuario
from apps.solicitacoes.models_acesso import AcessoInstitucional
from apps.solicitacoes.views.administracao_sistema import _enviar_senha_inicial


class OperadorForm(forms.Form):
    matricula = forms.CharField(max_length=30, label="Matrícula")
    nome = forms.CharField(max_length=150, label="Nome completo")
    cpf = forms.CharField(max_length=14, label="CPF")
    telefone = forms.CharField(max_length=25, label="Telefone")
    email = forms.EmailField(label="E-mail")

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})
        if instance:
            user = instance.usuario
            self.initial.update({
                "matricula": instance.matricula,
                "nome": user.get_full_name(),
                "cpf": instance.cpf,
                "telefone": instance.telefone,
                "email": user.email,
            })

    def clean_matricula(self):
        valor = self.cleaned_data["matricula"].strip()
        qs = AcessoInstitucional.objects.filter(matricula__iexact=valor)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esta matrícula já está cadastrada.")
        return valor

    def clean_cpf(self):
        valor = self.cleaned_data["cpf"].strip()
        qs = AcessoInstitucional.objects.filter(cpf=valor)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
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


def _operador_da_unidade(request, id):
    if not _eh_membro_unidade(request):
        return None
    return get_object_or_404(
        AcessoInstitucional.objects.select_related("usuario"),
        pk=id,
        perfil="OPERADOR",
        unidade_id=request.user.acesso_institucional.unidade_id,
    )


@login_required
def administracao_unidade_membro(request):
    if not _eh_membro_unidade(request):
        messages.error(request, "Somente membros de Unidade podem administrar operadores nesta tela.")
        return redirect("painel_gestao")

    acesso = request.user.acesso_institucional
    if request.method == "POST":
        form = OperadorForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            senha = data["matricula"]
            try:
                with transaction.atomic():
                    user = User.objects.create_user(username=data["matricula"], email=data["email"], password=senha, first_name=data["nome"], is_active=True)
                    AcessoInstitucional.objects.create(
                        usuario=user, matricula=data["matricula"], cpf=data["cpf"], telefone=data["telefone"],
                        perfil="OPERADOR", funcao="MEMBRO", cpr_id=acesso.unidade.cpr_id, unidade_id=acesso.unidade_id,
                        primeiro_acesso=True, ativo=True,
                    )
                    PerfilUsuario.objects.update_or_create(
                        usuario=user,
                        defaults={"perfil": "OPERADOR", "cpr_id": acesso.unidade.cpr_id, "unidade_id": acesso.unidade_id, "ativo": True},
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

    operadores = AcessoInstitucional.objects.filter(perfil="OPERADOR", unidade_id=acesso.unidade_id).select_related("usuario").order_by("usuario__first_name", "matricula")
    return render(request, "administracao_sistema/operador_membro.html", {"form": form, "acesso": acesso, "operadores": operadores})


@login_required
def editar_operador_membro(request, id):
    operador = _operador_da_unidade(request, id)
    if not operador:
        messages.error(request, "Você não pode alterar este operador.")
        return redirect("painel_gestao")
    user = operador.usuario
    if request.method == "POST":
        form = OperadorForm(request.POST, instance=operador)
        if form.is_valid():
            data = form.cleaned_data
            user.username = data["matricula"]
            user.first_name = data["nome"]
            user.email = data["email"]
            user.save(update_fields=["username", "first_name", "email"])
            operador.matricula = data["matricula"]
            operador.cpf = data["cpf"]
            operador.telefone = data["telefone"]
            operador.save(update_fields=["matricula", "cpf", "telefone", "atualizado_em"])
            messages.success(request, "Operador atualizado com sucesso.")
            return redirect("administracao_unidade_membro")
    else:
        form = OperadorForm(instance=operador)
    return render(request, "administracao_sistema/editar_operador_membro.html", {"form": form, "operador": operador})


@login_required
def ativar_operador_membro(request, id):
    operador = _operador_da_unidade(request, id)
    if not operador:
        messages.error(request, "Você não pode ativar este operador.")
        return redirect("painel_gestao")
    operador.ativo = True
    operador.usuario.is_active = True
    operador.save(update_fields=["ativo", "atualizado_em"])
    operador.usuario.save(update_fields=["is_active"])
    messages.success(request, "Operador ativado.")
    return redirect("administracao_unidade_membro")


@login_required
def desativar_operador_membro(request, id):
    operador = _operador_da_unidade(request, id)
    if not operador:
        messages.error(request, "Você não pode desativar este operador.")
        return redirect("painel_gestao")
    operador.ativo = False
    operador.usuario.is_active = False
    operador.save(update_fields=["ativo", "atualizado_em"])
    operador.usuario.save(update_fields=["is_active"])
    messages.success(request, "Operador desativado.")
    return redirect("administracao_unidade_membro")


@login_required
def excluir_operador_membro(request, id):
    operador = _operador_da_unidade(request, id)
    if not operador:
        messages.error(request, "Você não pode excluir este operador.")
        return redirect("painel_gestao")
    user = operador.usuario
    nome = user.get_full_name() or operador.matricula
    try:
        user.delete()
    except ProtectedError:
        messages.error(request, "Este operador possui registros vinculados e não pode ser excluído. Desative o acesso para preservar o histórico.")
        return redirect("administracao_unidade_membro")
    messages.success(request, f"Operador {nome} excluído definitivamente.")
    return redirect("administracao_unidade_membro")
