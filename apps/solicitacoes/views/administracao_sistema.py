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

PERFIS = [("COPPM", "COPPM"), ("CPR", "CPR"), ("UNIDADE", "Unidade")]
FUNCOES = [("GESTOR", "Gestor"), ("MEMBRO", "Membro")]

class UsuarioSistemaForm(forms.Form):
    matricula = forms.CharField(max_length=30, label="Matrícula")
    nome = forms.CharField(max_length=150, label="Nome completo")
    cpf = forms.CharField(max_length=14, label="CPF")
    telefone = forms.CharField(max_length=25, label="Telefone")
    email = forms.EmailField(label="E-mail de validação")
    perfil = forms.ChoiceField(choices=PERFIS, label="Âmbito")
    funcao = forms.ChoiceField(choices=FUNCOES, label="Função")
    cpr = forms.ModelChoiceField(queryset=CPR.objects.none(), required=False, label="CPR")
    unidade = forms.ModelChoiceField(queryset=Unidade.objects.none(), required=False, label="Unidade")
    ativo = forms.BooleanField(required=False, initial=True, label="Usuário ativo")

    def __init__(self, *args, instance=None, scope=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        self.scope = scope
        self.fields["cpr"].queryset = CPR.objects.filter(ativo=True).order_by("sigla")
        self.fields["unidade"].queryset = Unidade.objects.filter(ativo=True).select_related("cpr").order_by("nome")
        if instance:
            acesso = getattr(instance, "acesso_institucional", None)
            if acesso:
                self.initial.update({"matricula": acesso.matricula, "nome": instance.get_full_name(), "cpf": acesso.cpf, "telefone": acesso.telefone, "email": instance.email, "perfil": acesso.perfil, "funcao": acesso.funcao, "cpr": acesso.cpr_id, "unidade": acesso.unidade_id, "ativo": acesso.ativo and instance.is_active})

    def clean_matricula(self):
        valor = self.cleaned_data["matricula"].strip()
        qs = AcessoInstitucional.objects.filter(matricula__iexact=valor)
        if self.instance:
            qs = qs.exclude(usuario=self.instance)
        if qs.exists() or User.objects.filter(username=valor).exclude(pk=getattr(self.instance, "pk", None)).exists():
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
        if perfil == "CPR" and not cleaned.get("cpr"): self.add_error("cpr", "Selecione o CPR.")
        if perfil == "UNIDADE" and not cleaned.get("unidade"): self.add_error("unidade", "Selecione a unidade.")
        if perfil == "COPPM": cleaned["cpr"], cleaned["unidade"] = None, None
        if self.scope and not self.scope["desenvolvedor"]:
            if self.scope["perfil"] == "CPR": cleaned.update(perfil="CPR", cpr=self.scope["cpr"], funcao="MEMBRO")
            elif self.scope["perfil"] == "UNIDADE": cleaned.update(perfil="UNIDADE", cpr=self.scope["cpr"], unidade=self.scope["unidade"], funcao="MEMBRO")
        return cleaned

def _escopo(request):
    if request.user.is_superuser: return {"desenvolvedor": True, "perfil": None, "cpr": None, "unidade": None}
    acesso = getattr(request.user, "acesso_institucional", None)
    if not acesso or not acesso.ativo or acesso.funcao != "GESTOR": return None
    if acesso.perfil == "CPR" and acesso.cpr: return {"desenvolvedor": False, "perfil": "CPR", "cpr": acesso.cpr, "unidade": None}
    if acesso.perfil == "UNIDADE" and acesso.unidade: return {"desenvolvedor": False, "perfil": "UNIDADE", "cpr": acesso.unidade.cpr, "unidade": acesso.unidade}
    if acesso.perfil == "COPPM": return {"desenvolvedor": False, "perfil": "COPPM", "cpr": None, "unidade": None}
    return None

def _pode_gerenciar(scope, acesso):
    if not scope or not acesso: return False
    if scope["desenvolvedor"]: return True
    if acesso.funcao != "MEMBRO" or scope["perfil"] != acesso.perfil: return False
    if acesso.perfil == "COPPM": return True
    if acesso.perfil == "CPR": return acesso.cpr_id == scope["cpr"].id
    if acesso.perfil == "UNIDADE": return acesso.unidade_id == scope["unidade"].id
    return False

def _senha_inicial(): return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

def _enviar_senha_inicial(user, senha):
    send_mail("Seu acesso institucional ao SiEv", f"Olá, {user.get_full_name()}.\n\nSeu acesso institucional ao SiEv foi criado.\n\nMatrícula: {user.username}\nSenha inicial: {senha}\n\nNo primeiro acesso o sistema exigirá a troca desta senha.\nNunca compartilhe sua senha.", None, [user.email], fail_silently=False)

def _sincronizar_perfil_compat(user, data):
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
    perfil.perfil, perfil.cpr, perfil.unidade, perfil.ativo = data["perfil"], data["cpr"], data["unidade"], data["ativo"]
    perfil.save()

@login_required
def administracao_sistema(request):
    scope = _escopo(request)
    if not scope:
        messages.error(request, "Você não possui permissão para administrar usuários.")
        return redirect("painel_gestao")
    qs = AcessoInstitucional.objects.select_related("usuario", "cpr", "unidade")
    if not scope["desenvolvedor"]:
        if scope["perfil"] == "COPPM": qs = qs.filter(perfil="COPPM", funcao="MEMBRO")
        elif scope["perfil"] == "CPR": qs = qs.filter(perfil="CPR", funcao="MEMBRO", cpr=scope["cpr"])
        elif scope["perfil"] == "UNIDADE": qs = qs.filter(perfil="UNIDADE", funcao="MEMBRO", unidade=scope["unidade"])
    return render(request, "administracao_sistema/index.html", {"acessos": qs.order_by("usuario__first_name", "matricula"), "perfis": qs, "scope": scope})

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
                data["funcao"] = "MEMBRO"; data["perfil"] = scope["perfil"]
                if scope["perfil"] == "CPR": data["cpr"] = scope["cpr"]
                elif scope["perfil"] == "UNIDADE": data["unidade"], data["cpr"] = scope["unidade"], scope["cpr"]
            senha = _senha_inicial()
            try:
                with transaction.atomic():
                    user = User.objects.create_user(username=data["matricula"], email=data["email"], password=senha, first_name=data["nome"], is_active=data["ativo"])
                    AcessoInstitucional.objects.create(usuario=user, matricula=data["matricula"], cpf=data["cpf"], telefone=data["telefone"], perfil=data["perfil"], funcao=data["funcao"], cpr=data["cpr"], unidade=data["unidade"], primeiro_acesso=True, ativo=data["ativo"])
                    _sincronizar_perfil_compat(user, data)
                    _enviar_senha_inicial(user, senha)
            except Exception:
                form.add_error(None, "Não foi possível concluir o cadastro ou enviar a senha para o e-mail informado.")
            else:
                messages.success(request, "Usuário criado. A senha inicial foi enviada para o e-mail cadastrado.")
                return redirect("administracao_sistema")
    else: form = UsuarioSistemaForm(scope=scope)
    return render(request, "administracao_sistema/form.html", {"form": form, "novo": True, "scope": scope})

@login_required
def usuario_editar(request, id):
    scope, user = _escopo(request), get_object_or_404(User, pk=id)
    acesso = getattr(user, "acesso_institucional", None)
    if not scope or not _pode_gerenciar(scope, acesso):
        messages.error(request, "Você não pode alterar este cadastro."); return redirect("administracao_sistema")
    if request.method == "POST":
        form = UsuarioSistemaForm(request.POST, instance=user, scope=scope)
        if form.is_valid():
            data = form.cleaned_data
            if not scope["desenvolvedor"]: data.update(perfil=acesso.perfil, funcao=acesso.funcao, cpr=acesso.cpr, unidade=acesso.unidade)
            user.username, user.first_name, user.email, user.is_active = data["matricula"], data["nome"], data["email"], data["ativo"]
            user.save(update_fields=["username", "first_name", "email", "is_active"])
            acesso.matricula, acesso.cpf, acesso.telefone, acesso.perfil, acesso.funcao, acesso.cpr, acesso.unidade, acesso.ativo = data["matricula"], data["cpf"], data["telefone"], data["perfil"], data["funcao"], data["cpr"], data["unidade"], data["ativo"]
            acesso.save(); _sincronizar_perfil_compat(user, data)
            messages.success(request, "Cadastro atualizado."); return redirect("administracao_sistema")
    else: form = UsuarioSistemaForm(instance=user, scope=scope)
    return render(request, "administracao_sistema/form.html", {"form": form, "novo": False, "usuario": user, "scope": scope})

@login_required
def usuario_senha(request, id):
    if not request.user.is_superuser:
        messages.error(request, "Gestores não podem alterar senhas. O usuário deve usar o primeiro acesso ou 'Esqueci minha senha'."); return redirect("administracao_sistema")
    user = get_object_or_404(User, pk=id); acesso = getattr(user, "acesso_institucional", None)
    if not acesso: messages.error(request, "Este usuário não possui cadastro institucional."); return redirect("administracao_sistema")
    if request.method == "POST":
        senha = _senha_inicial(); user.set_password(senha); user.save(update_fields=["password"]); acesso.primeiro_acesso = True; acesso.save(update_fields=["primeiro_acesso", "atualizado_em"])
        try: _enviar_senha_inicial(user, senha); messages.success(request, "Nova senha provisória enviada para o e-mail do usuário.")
        except Exception: messages.error(request, "A senha foi redefinida, mas não foi possível enviar o e-mail. Verifique o serviço de e-mail.")
        return redirect("administracao_sistema")
    return render(request, "administracao_sistema/senha.html", {"usuario": user})

@login_required
def usuario_desativar(request, id):
    scope, user = _escopo(request), get_object_or_404(User, pk=id); acesso = getattr(user, "acesso_institucional", None)
    if not scope or not _pode_gerenciar(scope, acesso): messages.error(request, "Você não pode alterar este cadastro."); return redirect("administracao_sistema")
    acesso.ativo = False; acesso.save(update_fields=["ativo", "atualizado_em"]); user.is_active = False; user.save(update_fields=["is_active"])
    messages.success(request, "Usuário desativado."); return redirect("administracao_sistema")

@login_required
def usuario_excluir(request, id):
    if not request.user.is_superuser: messages.error(request, "Somente o desenvolvedor pode excluir usuários."); return redirect("administracao_sistema")
    user = get_object_or_404(User, pk=id)
    if user.is_superuser: messages.error(request, "O desenvolvedor principal não pode ser excluído por esta tela."); return redirect("administracao_sistema")
    if request.method != "POST": messages.error(request, "A exclusão deve ser confirmada pelo formulário."); return redirect("administracao_sistema")
    nome = user.get_full_name() or user.username; user.delete(); messages.success(request, f"Usuário {nome} excluído definitivamente."); return redirect("administracao_sistema")
