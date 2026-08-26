import hashlib
import secrets
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.hashers import check_password, make_password

from apps.solicitacoes.models_acesso import (
    AcessoInstitucional,
    CodigoNovoNavegador,
    DispositivoAutorizado,
)


COOKIE_DISPOSITIVO = "siev_dispositivo"
EXPIRACAO_DISPOSITIVO = 60 * 60 * 24 * 365
EXPIRACAO_CODIGO_MINUTOS = 10
MAX_TENTATIVAS_CODIGO = 5


def _hash_token(valor):
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def _rotulo_navegador(request):
    ua = request.META.get("HTTP_USER_AGENT", "")
    if "Edg/" in ua:
        return "Microsoft Edge"
    if "Chrome/" in ua:
        return "Google Chrome"
    if "Firefox/" in ua:
        return "Mozilla Firefox"
    if "Safari/" in ua:
        return "Safari"
    return "Navegador"


def _dispositivo_autorizado(request, usuario):
    token = request.COOKIES.get(COOKIE_DISPOSITIVO)
    if not token:
        return None
    dispositivo = DispositivoAutorizado.objects.filter(
        usuario=usuario,
        token_hash=_hash_token(token),
        ativo=True,
    ).first()
    if dispositivo:
        dispositivo.save(update_fields=["ultimo_acesso"])
    return dispositivo


def _enviar_codigo_novo_navegador(request, usuario):
    CodigoNovoNavegador.objects.filter(
        usuario=usuario,
        usado=False,
    ).update(usado=True)

    codigo = f"{secrets.randbelow(10000):04d}"
    registro = CodigoNovoNavegador.objects.create(
        usuario=usuario,
        codigo_hash=make_password(codigo),
        expira_em=timezone.now() + timedelta(minutes=EXPIRACAO_CODIGO_MINUTOS),
    )

    nome = usuario.get_full_name() or usuario.username
    send_mail(
        subject="Código de acesso ao SiEv",
        message=(
            f"Olá, {nome}.\n\n"
            f"Foi identificado um novo navegador tentando acessar o SiEv.\n\n"
            f"Seu código de confirmação é: {codigo}\n\n"
            f"O código é válido por {EXPIRACAO_CODIGO_MINUTOS} minutos e pode ser usado uma única vez.\n\n"
            "Se você não reconhece este acesso, não informe o código e procure o administrador do sistema."
        ),
        from_email=None,
        recipient_list=[usuario.email],
        fail_silently=False,
    )
    return registro


def _finalizar_login(request, usuario, acesso, next_url=None):
    login(request, usuario)
    request.session.pop("siev_usuario_pendente", None)
    request.session.pop("siev_codigo_pendente", None)
    request.session.pop("siev_next", None)

    if acesso.primeiro_acesso:
        return redirect("trocar_senha_primeiro_acesso")

    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("painel_gestao")


def login_gestao(request):
    if request.user.is_authenticated:
        logout(request)

    if request.method == "POST":
        matricula = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next", "").strip()

        usuario = authenticate(request, username=matricula, password=password)
        if usuario is None:
            messages.error(request, "Matrícula ou senha inválidos.")
            return render(request, "gestao/login.html", {"next": next_url})

        if usuario.is_superuser or usuario.is_staff:
            login(request, usuario)
            return redirect("painel_gestao")

        acesso = getattr(usuario, "acesso_institucional", None)
        if not acesso:
            messages.error(request, "Este usuário ainda não possui cadastro institucional de acesso.")
            return render(request, "gestao/login.html", {"next": next_url})

        if not acesso.ativo or not usuario.is_active:
            messages.error(request, "Seu acesso institucional está inativo.")
            return render(request, "gestao/login.html", {"next": next_url})

        if acesso.perfil == "CPR" and not acesso.cpr:
            messages.error(request, "O acesso está sem CPR vinculado.")
            return render(request, "gestao/login.html", {"next": next_url})
        if acesso.perfil == "UNIDADE" and not acesso.unidade:
            messages.error(request, "O acesso está sem Unidade vinculada.")
            return render(request, "gestao/login.html", {"next": next_url})
        if not usuario.email:
            messages.error(request, "O cadastro não possui e-mail para validação de segurança.")
            return render(request, "gestao/login.html", {"next": next_url})

        if _dispositivo_autorizado(request, usuario):
            return _finalizar_login(request, usuario, acesso, next_url)

        try:
            codigo = _enviar_codigo_novo_navegador(request, usuario)
        except Exception:
            messages.error(request, "Não foi possível enviar o código para o e-mail cadastrado. Procure o administrador.")
            return render(request, "gestao/login.html", {"next": next_url})

        request.session["siev_usuario_pendente"] = usuario.pk
        request.session["siev_codigo_pendente"] = codigo.pk
        request.session["siev_next"] = next_url
        request.session.set_expiry(10 * 60)
        return redirect("verificar_novo_navegador")

    return render(request, "gestao/login.html", {"next": request.GET.get("next", "")})


def verificar_novo_navegador(request):
    usuario_id = request.session.get("siev_usuario_pendente")
    codigo_id = request.session.get("siev_codigo_pendente")
    if not usuario_id or not codigo_id:
        messages.error(request, "A solicitação de acesso expirou. Faça o login novamente.")
        return redirect("login_gestao")

    usuario = get_object_or_404(User, pk=usuario_id, is_active=True)
    acesso = getattr(usuario, "acesso_institucional", None)
    codigo = get_object_or_404(CodigoNovoNavegador, pk=codigo_id, usuario=usuario)

    if codigo.usado or codigo.expira_em < timezone.now() or codigo.tentativas >= MAX_TENTATIVAS_CODIGO:
        messages.error(request, "O código expirou. Faça o login novamente para receber outro código.")
        request.session.pop("siev_usuario_pendente", None)
        request.session.pop("siev_codigo_pendente", None)
        request.session.pop("siev_next", None)
        return redirect("login_gestao")

    if request.method == "POST":
        informado = "".join(ch for ch in request.POST.get("codigo", "") if ch.isdigit())
        codigo.tentativas += 1
        codigo.save(update_fields=["tentativas"])

        if len(informado) != 4 or not check_password(informado, codigo.codigo_hash):
            restantes = max(0, MAX_TENTATIVAS_CODIGO - codigo.tentativas)
            if restantes == 0:
                codigo.usado = True
                codigo.save(update_fields=["usado"])
                messages.error(request, "Número máximo de tentativas atingido. Faça o login novamente.")
                return redirect("login_gestao")
            messages.error(request, f"Código inválido. Tentativas restantes: {restantes}.")
            return render(request, "gestao/verificar_navegador.html")

        codigo.usado = True
        codigo.save(update_fields=["usado"])

        token = secrets.token_urlsafe(32)
        DispositivoAutorizado.objects.create(
            usuario=usuario,
            token_hash=_hash_token(token),
            rotulo=_rotulo_navegador(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        resposta = _finalizar_login(request, usuario, acesso, request.session.get("siev_next"))
        resposta.set_cookie(
            COOKIE_DISPOSITIVO,
            token,
            max_age=EXPIRACAO_DISPOSITIVO,
            httponly=True,
            secure=request.is_secure(),
            samesite="Lax",
        )
        return resposta

    return render(request, "gestao/verificar_navegador.html")


@login_required
def trocar_senha_primeiro_acesso(request):
    acesso = getattr(request.user, "acesso_institucional", None)
    if not acesso or not acesso.primeiro_acesso:
        return redirect("painel_gestao")

    if request.method == "POST":
        form = SetPasswordForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            acesso.primeiro_acesso = False
            acesso.save(update_fields=["primeiro_acesso", "atualizado_em"])
            messages.success(request, "Senha definida com sucesso. Seu acesso está liberado.")
            return redirect("painel_gestao")
    else:
        form = SetPasswordForm(request.user)

    return render(request, "gestao/trocar_senha_primeiro_acesso.html", {"form": form})


def esqueci_senha(request):
    if request.method == "POST":
        identificador = request.POST.get("identificador", "").strip()
        acesso = AcessoInstitucional.objects.select_related("usuario").filter(
            models_q(identificador)
        ).first()
        if acesso and acesso.ativo and acesso.usuario.is_active and acesso.usuario.email:
            token = default_token_generator.make_token(acesso.usuario)
            uid = __import__("django.utils.http", fromlist=["urlsafe_base64_encode"]).urlsafe_base64_encode(
                __import__("django.utils.encoding", fromlist=["force_bytes"]).force_bytes(acesso.usuario.pk)
            )
            url = request.build_absolute_uri(
                reverse("redefinir_senha", kwargs={"uidb64": uid, "token": token})
            )
            send_mail(
                subject="Redefinição de senha - SiEv",
                message=(
                    f"Olá, {acesso.usuario.get_full_name() or acesso.matricula}.\n\n"
                    f"Use o link abaixo para criar uma nova senha:\n{url}\n\n"
                    "Se você não solicitou a alteração, ignore esta mensagem."
                ),
                from_email=None,
                recipient_list=[acesso.usuario.email],
                fail_silently=True,
            )
        return render(request, "gestao/esqueci_senha_enviado.html")

    return render(request, "gestao/esqueci_senha.html")


def models_q(identificador):
    from django.db.models import Q
    return Q(matricula__iexact=identificador) | Q(usuario__email__iexact=identificador)


def redefinir_senha(request, uidb64, token):
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        usuario = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        usuario = None

    if not usuario or not default_token_generator.check_token(usuario, token):
        return render(request, "gestao/link_senha_invalido.html")

    if request.method == "POST":
        form = SetPasswordForm(usuario, request.POST)
        if form.is_valid():
            form.save()
            acesso = getattr(usuario, "acesso_institucional", None)
            if acesso:
                acesso.primeiro_acesso = False
                acesso.save(update_fields=["primeiro_acesso", "atualizado_em"])
            return render(request, "gestao/senha_redefinida.html")
    else:
        form = SetPasswordForm(usuario)

    return render(request, "gestao/redefinir_senha.html", {"form": form})


@login_required
def logout_gestao(request):
    logout(request)
    resposta = redirect("portal")
    resposta.delete_cookie(COOKIE_DISPOSITIVO)
    return resposta
