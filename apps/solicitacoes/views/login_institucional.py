from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from .acesso import _dispositivo_autorizado, _enviar_codigo_novo_navegador, _finalizar_login
from ..acesso_regras import sincronizar_acesso


def login_gestao(request):
    if request.user.is_authenticated:
        logout(request)
    if request.method != "POST":
        return render(request, "gestao/login.html", {"next": request.GET.get("next", "")})
    matricula=(request.POST.get("username") or "").strip()
    password=request.POST.get("password") or ""
    next_url=(request.POST.get("next") or "").strip()
    usuario=authenticate(request,username=matricula,password=password)
    if usuario is None:
        messages.error(request,"Matrícula ou senha inválidos.")
        return render(request,"gestao/login.html",{"next":next_url})
    if usuario.is_superuser or usuario.is_staff:
        login(request,usuario); return redirect("painel_gestao")
    acesso=getattr(usuario,"acesso_institucional",None)
    if not acesso:
        legado=getattr(usuario,"perfil_siev",None)
        if legado and legado.ativo:
            acesso=sincronizar_acesso(usuario,perfil=legado.perfil,funcao="GESTOR",cpr=legado.cpr,unidade=legado.unidade,matricula=usuario.username,ativo=usuario.is_active,primeiro_acesso=False)
    if not acesso:
        messages.error(request,"Este usuário ainda não possui cadastro institucional de acesso.")
        return render(request,"gestao/login.html",{"next":next_url})
    if not acesso.ativo or not usuario.is_active:
        messages.error(request,"Seu acesso institucional está inativo.")
        return render(request,"gestao/login.html",{"next":next_url})
    if acesso.perfil=="CPR" and not acesso.cpr_id:
        messages.error(request,"O acesso está sem CPR vinculado."); return render(request,"gestao/login.html",{"next":next_url})
    if acesso.perfil in {"UNIDADE","OPERADOR"} and not acesso.unidade_id:
        messages.error(request,"O acesso está sem Unidade vinculada."); return render(request,"gestao/login.html",{"next":next_url})
    if not usuario.email:
        messages.error(request,"O cadastro não possui e-mail para validação de segurança."); return render(request,"gestao/login.html",{"next":next_url})
    if _dispositivo_autorizado(request,usuario):
        return _finalizar_login(request,usuario,acesso,next_url)
    try:
        codigo=_enviar_codigo_novo_navegador(request,usuario)
    except Exception:
        messages.error(request,"Não foi possível enviar o código para o e-mail cadastrado. Procure o administrador.")
        return render(request,"gestao/login.html",{"next":next_url})
    request.session["siev_usuario_pendente"]=usuario.pk
    request.session["siev_codigo_pendente"]=codigo.pk
    request.session["siev_next"]=next_url
    request.session.set_expiry(600)
    return redirect("verificar_novo_navegador")
