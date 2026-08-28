import secrets
import string
from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from apps.solicitacoes.models import CPR, PerfilUsuario, Solicitacao, TransferenciaSolicitacao, Unidade
from apps.solicitacoes.models_acesso import AcessoInstitucional
from apps.solicitacoes.permissoes import pode_ver_solicitacao


class UsuarioFluxoForm(forms.Form):
    matricula=forms.CharField(max_length=30,label="Matrícula")
    nome=forms.CharField(max_length=150,label="Nome completo")
    cpf=forms.CharField(max_length=14,label="CPF")
    telefone=forms.CharField(max_length=25,label="Telefone")
    email=forms.EmailField(label="E-mail")
    perfil=forms.ChoiceField(choices=[("COPPM","Membro COPPM"),("CPR","Membro CPR"),("UNIDADE","Membro de Unidade"),("OPERADOR","Operador")],label="Tipo de acesso")
    funcao=forms.ChoiceField(choices=[("GESTOR","Gestor"),("MEMBRO","Membro")],label="Função",required=False)
    cpr=forms.ModelChoiceField(queryset=CPR.objects.none(),required=False,label="CPR")
    unidade=forms.ModelChoiceField(queryset=Unidade.objects.none(),required=False,label="Unidade")
    ativo=forms.BooleanField(required=False,initial=True,label="Usuário ativo")

    def __init__(self,*args,scope=None,instance=None,**kwargs):
        super().__init__(*args,**kwargs); self.scope=scope; self.instance=instance
        self.fields["cpr"].queryset=CPR.objects.filter(ativo=True).order_by("sigla")
        self.fields["unidade"].queryset=Unidade.objects.filter(ativo=True).select_related("cpr").order_by("nome")
        if scope and not scope["desenvolvedor"]:
            if scope["perfil"]=="COPPM":
                self.fields["perfil"].choices=[("COPPM","Membro COPPM")]
                self.fields["cpr"].queryset=CPR.objects.none(); self.fields["unidade"].queryset=Unidade.objects.none()
            elif scope["perfil"]=="CPR":
                self.fields["perfil"].choices=[("CPR","Membro CPR"),("OPERADOR","Operador")]
                self.fields["cpr"].queryset=CPR.objects.filter(pk=scope["cpr"].pk)
                self.fields["unidade"].queryset=Unidade.objects.filter(cpr=scope["cpr"],ativo=True).order_by("nome")
            elif scope["perfil"]=="UNIDADE":
                self.fields["perfil"].choices=[("UNIDADE","Membro de Unidade"),("OPERADOR","Operador")]
                self.fields["cpr"].queryset=CPR.objects.filter(pk=scope["cpr"].pk)
                self.fields["unidade"].queryset=Unidade.objects.filter(pk=scope["unidade"].pk)
            self.fields["funcao"].widget=forms.HiddenInput(); self.fields["funcao"].initial="MEMBRO"
        if instance:
            a=getattr(instance,"acesso_institucional",None)
            if a: self.initial.update(matricula=a.matricula,nome=instance.get_full_name(),cpf=a.cpf or "",telefone=a.telefone,email=instance.email,perfil=a.perfil,funcao=a.funcao,cpr=a.cpr_id,unidade=a.unidade_id,ativo=a.ativo and instance.is_active)

    def clean_matricula(self):
        v=self.cleaned_data["matricula"].strip(); qs=AcessoInstitucional.objects.filter(matricula__iexact=v)
        if self.instance: qs=qs.exclude(usuario=self.instance)
        if qs.exists(): raise forms.ValidationError("Esta matrícula já está cadastrada.")
        return v
    def clean_cpf(self):
        v=self.cleaned_data["cpf"].strip(); qs=AcessoInstitucional.objects.filter(cpf=v)
        if self.instance: qs=qs.exclude(usuario=self.instance)
        if v and qs.exists(): raise forms.ValidationError("Este CPF já está cadastrado.")
        return v
    def clean(self):
        c=super().clean(); p=c.get("perfil"); u=c.get("unidade"); r=c.get("cpr")
        if p in {"UNIDADE","OPERADOR"} and not u: self.add_error("unidade","Selecione a unidade.")
        if p=="CPR" and not r: self.add_error("cpr","Selecione o CPR.")
        if u and r and u.cpr_id!=r.id: self.add_error("unidade","A unidade não pertence ao CPR informado.")
        if self.scope and not self.scope["desenvolvedor"]:
            if self.scope["perfil"]=="COPPM" and p!="COPPM": self.add_error("perfil","Apenas membros da COPPM podem ser cadastrados aqui.")
            if self.scope["perfil"]=="CPR" and p not in {"CPR","OPERADOR"}: self.add_error("perfil","Tipo de acesso inválido para este CPR.")
            if self.scope["perfil"]=="UNIDADE" and p not in {"UNIDADE","OPERADOR"}: self.add_error("perfil","Tipo de acesso inválido para esta Unidade.")
            if self.scope["perfil"]=="CPR" and p=="OPERADOR" and (not u or u.cpr_id!=self.scope["cpr"].id): self.add_error("unidade","O operador deve pertencer ao seu CPR.")
            if self.scope["perfil"]=="UNIDADE" and (not u or u.id!=self.scope["unidade"].id): self.add_error("unidade","O usuário deve pertencer à sua Unidade.")
            c["funcao"]="MEMBRO"
        return c


def escopo(request):
    if request.user.is_superuser or request.user.is_staff: return {"desenvolvedor":True,"perfil":None,"cpr":None,"unidade":None}
    a=getattr(request.user,"acesso_institucional",None)
    if not a or not a.ativo or not request.user.is_active: return None
    if a.perfil=="COPPM": return {"desenvolvedor":False,"perfil":"COPPM","cpr":None,"unidade":None,"funcao":a.funcao}
    if a.perfil=="CPR" and a.cpr_id: return {"desenvolvedor":False,"perfil":"CPR","cpr":a.cpr,"unidade":None,"funcao":a.funcao}
    if a.perfil=="UNIDADE" and a.unidade_id: return {"desenvolvedor":False,"perfil":"UNIDADE","cpr":a.unidade.cpr,"unidade":a.unidade,"funcao":a.funcao}
    return None


def pode_gerenciar(scope,a):
    if not scope or not a: return False
    if scope["desenvolvedor"]: return True
    if scope["funcao"]=="GESTOR":
        if scope["perfil"]=="COPPM": return a.perfil=="COPPM" and a.funcao=="MEMBRO"
        if scope["perfil"]=="CPR": return a.perfil in {"CPR","OPERADOR"} and a.cpr_id==scope["cpr"].id and a.funcao=="MEMBRO"
        if scope["perfil"]=="UNIDADE": return a.perfil in {"UNIDADE","OPERADOR"} and a.unidade_id==scope["unidade"].id and a.funcao=="MEMBRO"
    if scope["funcao"]=="MEMBRO": return a.perfil=="OPERADOR" and ((scope["perfil"]=="CPR" and a.cpr_id==scope["cpr"].id) or (scope["perfil"]=="UNIDADE" and a.unidade_id==scope["unidade"].id))
    return False


def _senha(): return "".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(12))

def _compat(user,a):
    PerfilUsuario.objects.update_or_create(usuario=user,defaults={"perfil":a.perfil if a.perfil!="OPERADOR" else "UNIDADE","cpr":a.cpr,"unidade":a.unidade,"ativo":a.ativo})

@login_required
def administracao_sistema(request):
    s=escopo(request)
    if not s: messages.error(request,"Você não possui permissão para administrar usuários."); return redirect("painel_gestao")
    qs=AcessoInstitucional.objects.select_related("usuario","cpr","unidade")
    if not s["desenvolvedor"]:
        if s["perfil"]=="COPPM": qs=qs.filter(perfil="COPPM",funcao="MEMBRO")
        elif s["perfil"]=="CPR": qs=qs.filter(perfil__in=["CPR","OPERADOR"],cpr=s["cpr"])
        elif s["perfil"]=="UNIDADE": qs=qs.filter(perfil__in=["UNIDADE","OPERADOR"],unidade=s["unidade"])
        if s["funcao"]=="MEMBRO": qs=qs.filter(perfil="OPERADOR")
    return render(request,"administracao_sistema/index.html",{"acessos":qs.order_by("usuario__first_name","matricula"),"perfis":qs,"scope":s})

@login_required
def usuario_novo(request):
    s=escopo(request)
    if not s or (not s["desenvolvedor"] and s["funcao"] not in {"GESTOR","MEMBRO"}): messages.error(request,"Você não possui permissão para cadastrar usuários."); return redirect("painel_gestao")
    if request.method=="POST":
        f=UsuarioFluxoForm(request.POST,scope=s)
        if f.is_valid():
            d=f.cleaned_data; p=d["perfil"]
            if not s["desenvolvedor"]:
                d["funcao"]="MEMBRO"
                if s["perfil"]=="COPPM": d.update(perfil="COPPM",cpr=None,unidade=None)
                elif s["perfil"]=="CPR": d["cpr"]=s["cpr"]
                elif s["perfil"]=="UNIDADE": d.update(cpr=s["cpr"],unidade=s["unidade"])
            senha=_senha()
            try:
                with transaction.atomic():
                    user=User.objects.create_user(username=d["matricula"],email=d["email"],password=senha,first_name=d["nome"],is_active=d["ativo"])
                    a=AcessoInstitucional.objects.create(usuario=user,matricula=d["matricula"],cpf=d["cpf"] or None,telefone=d["telefone"],perfil=d["perfil"],funcao=d["funcao"],cpr=d["cpr"],unidade=d["unidade"],primeiro_acesso=True,ativo=d["ativo"])
                    _compat(user,a)
                    send_mail("Seu acesso institucional ao SiEv",f"Olá, {user.get_full_name()}.\n\nMatrícula: {a.matricula}\nSenha inicial: {senha}\n\nNo primeiro acesso será solicitada a troca da senha.",None,[user.email],fail_silently=False)
            except Exception as e:
                if "user" in locals() and user.pk: user.delete()
                f.add_error(None,"Não foi possível concluir o cadastro ou enviar a senha para o e-mail informado.")
            else: messages.success(request,"Usuário criado com acesso institucional."); return redirect("administracao_sistema")
    else: f=UsuarioFluxoForm(scope=s)
    return render(request,"administracao_sistema/form.html",{"form":f,"novo":True,"scope":s})

@login_required
def usuario_editar(request,id):
    s=escopo(request); user=get_object_or_404(User,pk=id); a=getattr(user,"acesso_institucional",None)
    if not pode_gerenciar(s,a): messages.error(request,"Você não pode alterar este cadastro."); return redirect("administracao_sistema")
    if request.method=="POST":
        f=UsuarioFluxoForm(request.POST,scope=s,instance=user)
        if f.is_valid():
            d=f.cleaned_data; user.first_name=d["nome"]; user.email=d["email"]; user.is_active=d["ativo"]; user.save()
            a.matricula=d["matricula"]; a.cpf=d["cpf"] or None; a.telefone=d["telefone"]; a.ativo=d["ativo"]; a.save(); _compat(user,a)
            messages.success(request,"Cadastro atualizado."); return redirect("administracao_sistema")
    else: f=UsuarioFluxoForm(scope=s,instance=user)
    return render(request,"administracao_sistema/form.html",{"form":f,"novo":False,"usuario":user,"scope":s})

@login_required
def usuario_senha(request,id):
    if not request.user.is_superuser and not request.user.is_staff: messages.error(request,"Somente o administrador pode redefinir senhas."); return redirect("administracao_sistema")
    user=get_object_or_404(User,pk=id); a=getattr(user,"acesso_institucional",None)
    if not a: messages.error(request,"Este usuário não possui acesso institucional."); return redirect("administracao_sistema")
    if request.method=="POST":
        senha=_senha(); user.set_password(senha); user.save(update_fields=["password"]); a.primeiro_acesso=True; a.save(update_fields=["primeiro_acesso","atualizado_em"])
        try: send_mail("Nova senha provisória - SiEv",f"Matrícula: {a.matricula}\nSenha inicial: {senha}",None,[user.email],fail_silently=False)
        except Exception: messages.error(request,"Senha redefinida, mas o e-mail não pôde ser enviado.")
        else: messages.success(request,"Nova senha provisória enviada.")
        return redirect("administracao_sistema")
    return render(request,"administracao_sistema/senha.html",{"usuario":user})

@login_required
def usuario_desativar(request,id):
    s=escopo(request); user=get_object_or_404(User,pk=id); a=getattr(user,"acesso_institucional",None)
    if not pode_gerenciar(s,a) or user.pk==request.user.pk: messages.error(request,"Você não pode desativar este usuário."); return redirect("administracao_sistema")
    a.ativo=False; a.save(update_fields=["ativo","atualizado_em"]); user.is_active=False; user.save(update_fields=["is_active"]); return redirect("administracao_sistema")

@login_required
def transferir_solicitacao_segura(request,id):
    s=escopo(request); sol=get_object_or_404(Solicitacao.objects.select_related("unidade"),pk=id)
    if not s or not pode_ver_solicitacao(request.user,sol): messages.error(request,"Você não possui acesso a esta solicitação."); return redirect("aprovacoes")
    if s["funcao"] not in {"GESTOR","MEMBRO"}: messages.error(request,"Você não possui permissão para transferir solicitações."); return redirect("aprovacoes")
    unidades=Unidade.objects.filter(ativo=True).exclude(pk=sol.unidade_id)
    if s["perfil"]=="UNIDADE": unidades=unidades.filter(cpr=s["cpr"])
    elif s["perfil"]=="CPR": unidades=unidades.filter(cpr=s["cpr"])
    if request.method=="POST":
        dest=get_object_or_404(unidades,pk=request.POST.get("unidade_destino")); motivo=request.POST.get("motivo","").strip()
        with transaction.atomic():
            TransferenciaSolicitacao.objects.create(solicitacao=sol,unidade_origem=sol.unidade,unidade_destino=dest,usuario=request.user,motivo=motivo)
            sol.unidade=dest; sol.origem="TRANSFERIDA"; sol.save(update_fields=["unidade","origem","atualizado_em"])
        return redirect("aprovacoes")
    return render(request,"gestao/transferir_solicitacao.html",{"solicitacao":sol,"unidades":unidades})
