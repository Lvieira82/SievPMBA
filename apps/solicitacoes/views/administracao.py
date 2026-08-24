from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from datetime import timedelta
from django.utils import timezone


from apps.solicitacoes.models import (
    PerfilUsuario,
    MatriculaAutorizada,
    COPPM,
    CPR,
    Unidade,
    Municipio,
    Bairro,
    TipoEvento,
    TipoDocumento,
    UsuarioPerfil,
    Solicitacao,
    TransferenciaSolicitacao,
)

from apps.solicitacoes.forms import UsuarioGestaoForm

# ==========================================================
# ACESSO INSTITUCIONAL
# ==========================================================

def login_gestao(request):

    # ==================================================
    # USUÁRIO JÁ AUTENTICADO
    # ==================================================

    def login_gestao(request):

        # ==================================================
        # ACESSO INSTITUCIONAL
        # ==================================================
        #
        # Ao entrar pela Área Institucional,
        # sempre apresentar a tela de login.
        #
        # Se já existir uma sessão aberta, encerramos
        # a sessão anterior antes de apresentar o login.
        # ==================================================

        if request.user.is_authenticated:
            logout(request)

        # ==================================================
        # LOGIN
        # ==================================================

        if request.method == "POST":

            username = request.POST.get(
                "username",
                ""
            ).strip()

            password = request.POST.get(
                "password",
                ""
            )

            if not username or not password:

                messages.error(
                    request,
                    "Informe o usuário e a senha."
                )

                return render(
                    request,
                    "gestao/login.html"
                )

            usuario = authenticate(
                request,
                username=username,
                password=password
            )

            if usuario is None:

                messages.error(
                    request,
                    "Usuário ou senha inválidos."
                )

                return render(
                    request,
                    "gestao/login.html"
                )

            # ==================================================
            # DESENVOLVEDOR / ADMINISTRADOR
            # ==================================================

            if usuario.is_superuser or usuario.is_staff:

                login(
                    request,
                    usuario
                )

                return redirect(
                    "painel_gestao"
                )

            # ==================================================
            # USUÁRIO INSTITUCIONAL
            # ==================================================

            perfil = getattr(
                usuario,
                "perfil_siev",
                None
            )

            if not perfil:

                messages.error(
                    request,
                    "Este usuário não possui um perfil institucional no SiEv."
                )

                return render(
                    request,
                    "gestao/login.html"
                )

            if not perfil.ativo:

                messages.error(
                    request,
                    "Seu perfil institucional está inativo."
                )

                return render(
                    request,
                    "gestao/login.html"
                )

            # ==================================================
            # COPPM
            # ==================================================

            if perfil.perfil == "COPPM":

                login(
                    request,
                    usuario
                )

                return redirect(
                    "painel_gestao"
                )

            # ==================================================
            # CPR
            # ==================================================

            if perfil.perfil == "CPR":

                if not perfil.cpr:

                    messages.error(
                        request,
                        "Seu perfil de CPR não possui um CPR vinculado."
                    )

                    return render(
                        request,
                        "gestao/login.html"
                    )

                login(
                    request,
                    usuario
                )

                return redirect(
                    "painel_gestao"
                )

            # ==================================================
            # UNIDADE
            # ==================================================

            if perfil.perfil == "UNIDADE":

                if not perfil.unidade:

                    messages.error(
                        request,
                        "Seu perfil de Unidade não possui uma Unidade vinculada."
                    )

                    return render(
                        request,
                        "gestao/login.html"
                    )

                login(
                    request,
                    usuario
                )

                return redirect(
                    "painel_gestao"
                )

            messages.error(
                request,
                "Perfil institucional não reconhecido."
            )

            return render(
                request,
                "gestao/login.html"
            )

        # ==================================================
        # EXIBIR TELA DE LOGIN
        # ==================================================

        return render(
            request,
            "gestao/login.html"
        )

    # ==================================================
    # LOGIN
    # ==================================================

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        if not username or not password:

            messages.error(
                request,
                "Informe o usuário e a senha."
            )

            return render(
                request,
                "gestao/login.html"
            )

        usuario = authenticate(
            request,
            username=username,
            password=password
        )

        if usuario is None:

            messages.error(
                request,
                "Usuário ou senha inválidos."
            )

            return render(
                request,
                "gestao/login.html"
            )

        # ==================================================
        # DESENVOLVEDOR / ADMINISTRADOR
        # ==================================================

        if usuario.is_superuser or usuario.is_staff:

            login(
                request,
                usuario
            )

            return redirect(
                "painel_gestao"
            )

        # ==================================================
        # USUÁRIO INSTITUCIONAL
        # ==================================================

        perfil = getattr(
            usuario,
            "perfil_siev",
            None
        )

        if not perfil:

            messages.error(
                request,
                "Este usuário não possui um perfil institucional no SiEv."
            )

            return render(
                request,
                "gestao/login.html"
            )

        # ==================================================
        # PERFIL INATIVO
        # ==================================================

        if not perfil.ativo:

            messages.error(
                request,
                "Seu perfil institucional está inativo."
            )

            return render(
                request,
                "gestao/login.html"
            )

        # ==================================================
        # COPPM
        # ==================================================

        if perfil.perfil == "COPPM":

            login(
                request,
                usuario
            )

            return redirect(
                "painel_gestao"
            )

        # ==================================================
        # CPR
        # ==================================================

        if perfil.perfil == "CPR":

            if not perfil.cpr:

                messages.error(
                    request,
                    "Seu perfil de CPR não possui um CPR vinculado."
                )

                return render(
                    request,
                    "gestao/login.html"
                )

            login(
                request,
                usuario
            )

            return redirect(
                "painel_gestao"
            )

        # ==================================================
        # UNIDADE
        # ==================================================

        if perfil.perfil == "UNIDADE":

            if not perfil.unidade:

                messages.error(
                    request,
                    "Seu perfil de Unidade não possui uma Unidade vinculada."
                )

                return render(
                    request,
                    "gestao/login.html"
                )

            login(
                request,
                usuario
            )

            return redirect(
                "painel_gestao"
            )

        # ==================================================
        # PERFIL INVÁLIDO
        # ==================================================

        messages.error(
            request,
            "Perfil institucional não reconhecido."
        )

        return render(
            request,
            "gestao/login.html"
        )

    return render(
        request,
        "gestao/login.html"
    )


@login_required
def logout_gestao(request):

    logout(request)

    return redirect("portal")

# ==========================================================
# PAINEL INSTITUCIONAL
# ==========================================================

@login_required
def painel_gestao(request):

    hoje = timezone.localdate()

    # ==================================================
    # DESENVOLVEDOR / SUPERUSUÁRIO
    # ==================================================

    if request.user.is_superuser or request.user.is_staff:

        context = {
            "perfil": None,
            "nivel": "DESENVOLVEDOR",
            "titulo_painel": "Administração do Sistema",

            "pendentes_opo": Solicitacao.objects.filter(
                status="PENDENTE"
            ).count(),

            "eventos_semana": Solicitacao.objects.filter(
                data_evento__gte=hoje,
                data_evento__lte=hoje + timedelta(days=7)
            ).count(),

            "eventos_mes": Solicitacao.objects.filter(
                data_evento__year=hoje.year,
                data_evento__month=hoje.month
            ).count(),

            "proximos_eventos": Solicitacao.objects.filter(
                data_evento__gte=hoje
            ).order_by(
                "data_evento",
                "hora_inicio"
            )[:5],

            "usuarios": User.objects.count(),
        }

        return render(
            request,
            "gestao/painel_gestao.html",
            context
        )

    # ==================================================
    # USUÁRIO INSTITUCIONAL
    # ==================================================

    perfil = getattr(
        request.user,
        "perfil_siev",
        None
    )

    if not perfil:

        messages.error(
            request,
            "Usuário sem perfil institucional."
        )

        return redirect("login_gestao")

    if not perfil.ativo:

        messages.error(
            request,
            "Seu perfil institucional está inativo."
        )

        return redirect("logout_gestao")

    # ==================================================
    # COPPM
    # ==================================================

    if perfil.perfil == "COPPM":

        solicitacoes = Solicitacao.objects.all()

        titulo_painel = "Gestão COPPM"

    # ==================================================
    # CPR
    # ==================================================

    elif perfil.perfil == "CPR":

        solicitacoes = Solicitacao.objects.filter(
            unidade__cpr=perfil.cpr
        )

        titulo_painel = f"Gestão {perfil.cpr}"

    # ==================================================
    # UNIDADE
    # ==================================================

    elif perfil.perfil == "UNIDADE":

        solicitacoes = Solicitacao.objects.filter(
            unidade=perfil.unidade
        )

        titulo_painel = f"Gestão {perfil.unidade}"

    else:

        messages.error(
            request,
            "Perfil institucional inválido."
        )

        return redirect("logout_gestao")

    context = {
        "perfil": perfil,
        "nivel": perfil.perfil,
        "titulo_painel": titulo_painel,

        "pendentes_opo": solicitacoes.filter(
            status="PENDENTE"
        ).count(),

        "eventos_semana": solicitacoes.filter(
            data_evento__gte=hoje,
            data_evento__lte=hoje + timedelta(days=7)
        ).count(),

        "eventos_mes": solicitacoes.filter(
            data_evento__year=hoje.year,
            data_evento__month=hoje.month
        ).count(),

        "proximos_eventos": solicitacoes.filter(
            data_evento__gte=hoje
        ).order_by(
            "data_evento",
            "hora_inicio"
        )[:5],

        "usuarios": PerfilUsuario.objects.count(),
    }

    return render(
        request,
        "gestao/painel_gestao.html",
        context
    )
# ==========================================================
# PAINEL ADMINISTRATIVO
# ==========================================================

@login_required
def painel_administracao(request):

    context = {

        "usuarios": UsuarioPerfil.objects.count(),

        "cprs": CPR.objects.count(),

        "unidades": Unidade.objects.count(),

        "municipios": Municipio.objects.count(),

        "tipos_evento": TipoEvento.objects.count(),

        "tipos_documento": TipoDocumento.objects.count(),

    }

    return render(
        request,
        "administracao/index.html",
        context
    )


# ==========================================================
# USUÁRIOS - ÁREA ADMINISTRATIVA TÉCNICA
# ==========================================================

@login_required
def usuarios(request):

    usuarios = (
        UsuarioPerfil.objects
        .select_related(
            "usuario",
            "cpr",
            "unidade",
        )
        .all()
        .order_by(
            "usuario__first_name"
        )
    )

    return render(
        request,
        "administracao/usuarios.html",
        {
            "usuarios": usuarios
        }
    )


# ==========================================================
# CPRs
# ==========================================================

@login_required
def cprs(request):

    lista = CPR.objects.all().order_by("nome")

    return render(
        request,
        "administracao/cprs.html",
        {
            "lista": lista
        }
    )


# ==========================================================
# UNIDADES
# ==========================================================

@login_required
def unidades(request):

    lista = (
        Unidade.objects
        .select_related("cpr")
        .order_by("nome")
    )

    return render(
        request,
        "administracao/unidades.html",
        {
            "lista": lista
        }
    )


# ==========================================================
# MUNICÍPIOS
# ==========================================================

@login_required
def municipios(request):

    lista = Municipio.objects.order_by("nome")

    return render(
        request,
        "administracao/municipios.html",
        {
            "lista": lista
        }
    )


# ==========================================================
# BAIRROS
# ==========================================================

@login_required
def bairros(request):

    lista = (
        Bairro.objects
        .select_related("municipio")
        .order_by(
            "municipio__nome",
            "nome"
        )
    )

    return render(
        request,
        "administracao/bairros.html",
        {
            "lista": lista
        }
    )


# ==========================================================
# TIPOS DE EVENTO
# ==========================================================

@login_required
def tipos_evento(request):

    lista = TipoEvento.objects.order_by("nome")

    return render(
        request,
        "administracao/tipos_evento.html",
        {
            "lista": lista
        }
    )


# ==========================================================
# TIPOS DE DOCUMENTO
# ==========================================================

@login_required
def tipos_documento(request):

    lista = TipoDocumento.objects.order_by("nome")

    return render(
        request,
        "administracao/tipos_documento.html",
        {
            "lista": lista
        }
    )


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

@login_required
def configuracoes(request):

    return render(
        request,
        "administracao/configuracoes.html"
    )


# ==========================================================
# BACKUP
# ==========================================================

@login_required
def backup(request):

    messages.info(
        request,
        "Função disponível em breve."
    )

    return redirect(
        "painel_administracao"
    )


# ==========================================================
# FUNÇÃO AUXILIAR
# IDENTIFICA O PERFIL DO GESTOR LOGADO
# ==========================================================

def obter_perfil_gestor(request):

    perfil = getattr(
        request.user,
        "perfil_siev",
        None
    )

    if not perfil:
        return None

    if not perfil.ativo:
        return None

    return perfil


# ==========================================================
# USUÁRIOS DOS GESTORES
#
# COPPM  -> todos
# CPR    -> usuários do CPR
# UNIDADE -> usuários da unidade
# ==========================================================

@login_required
def usuarios_unidade(request):

    perfil = obter_perfil_gestor(request)

    if not perfil:

        messages.error(
            request,
            "Seu usuário não possui um perfil de gestão ativo."
        )

        return redirect("painel_gestao")

    # ======================================================
    # GESTOR COPPM
    # ======================================================

    if perfil.perfil == "COPPM":

        usuarios = (
            PerfilUsuario.objects
            .filter(
                ativo=True
            )
            .select_related(
                "usuario",
                "cpr",
                "unidade",
            )
            .order_by(
                "usuario__first_name",
                "usuario__last_name",
            )
        )

    # ======================================================
    # GESTOR CPR
    # ======================================================

    elif perfil.perfil == "CPR":

        if not perfil.cpr:

            messages.error(
                request,
                "Seu perfil não possui um CPR vinculado."
            )

            return redirect("painel_gestao")

        usuarios = (
            PerfilUsuario.objects
            .filter(
                cpr=perfil.cpr,
                ativo=True
            )
            .select_related(
                "usuario",
                "cpr",
                "unidade",
            )
            .order_by(
                "usuario__first_name",
                "usuario__last_name",
            )
        )

    # ======================================================
    # GESTOR DE UNIDADE
    # ======================================================

    elif perfil.perfil == "UNIDADE":

        if not perfil.unidade:

            messages.error(
                request,
                "Seu perfil não possui uma Unidade vinculada."
            )

            return redirect("painel_gestao")

        usuarios = (
            PerfilUsuario.objects
            .filter(
                unidade=perfil.unidade,
                ativo=True
            )
            .select_related(
                "usuario",
                "cpr",
                "unidade",
            )
            .order_by(
                "usuario__first_name",
                "usuario__last_name",
            )
        )

    else:

        messages.error(
            request,
            "Perfil de gestão inválido."
        )

        return redirect("painel_gestao")

    return render(
        request,
        "gestao/usuarios_unidade.html",
        {
            "usuarios": usuarios,
            "perfil": perfil,
            "unidade": perfil.unidade,
            "cpr": perfil.cpr,
        }
    )


# ==========================================================
# CADASTRAR USUÁRIO
# ==========================================================

@login_required
def cadastrar_usuario_unidade(request):

    perfil = obter_perfil_gestor(request)

    if not perfil:

        messages.error(
            request,
            "Seu usuário não possui um perfil de gestão ativo."
        )

        return redirect("painel_gestao")

    # ======================================================
    # UNIDADE
    # ======================================================

    if perfil.perfil == "UNIDADE":

        if not perfil.unidade:

            messages.error(
                request,
                "Seu perfil não possui uma Unidade vinculada."
            )

            return redirect("painel_gestao")

        unidade = perfil.unidade

    # ======================================================
    # CPR
    # ======================================================

    elif perfil.perfil == "CPR":

        if not perfil.cpr:

            messages.error(
                request,
                "Seu perfil não possui um CPR vinculado."
            )

            return redirect("painel_gestao")

        unidade = None

    # ======================================================
    # COPPM
    # ======================================================

    elif perfil.perfil == "COPPM":

        unidade = None

    else:

        messages.error(
            request,
            "Perfil de gestão inválido."
        )

        return redirect("painel_gestao")

    # ======================================================
    # POST
    # ======================================================

    if request.method == "POST":

        form = UsuarioGestaoForm(
            request.POST
        )

        if form.is_valid():

            try:

                with transaction.atomic():

                    # ======================================
                    # DADOS DO FORMULÁRIO
                    # ======================================

                    username = form.cleaned_data[
                        "username"
                    ]

                    email = form.cleaned_data[
                        "email"
                    ]

                    senha = form.cleaned_data[
                        "senha"
                    ]

                    nome = form.cleaned_data[
                        "nome"
                    ]

                    matricula = form.cleaned_data[
                        "matricula"
                    ]

                    posto = form.cleaned_data[
                        "posto"
                    ]

                    # ======================================
                    # VERIFICA USER EXISTENTE
                    # ======================================

                    if User.objects.filter(
                        username=username
                    ).exists():

                        form.add_error(
                            "username",
                            "Este nome de usuário já existe."
                        )

                        return render(
                            request,
                            "gestao/cadastrar_usuario.html",
                            {
                                "form": form,
                                "unidade": unidade,
                                "perfil": perfil,
                            }
                        )

                    # ======================================
                    # LOCALIZAÇÃO DO NOVO USUÁRIO
                    # ======================================

                    nova_unidade = unidade
                    novo_cpr = None

                    # --------------------------------------------------
                    # GESTOR DE UNIDADE
                    # --------------------------------------------------

                    if perfil.perfil == "UNIDADE":

                        novo_cpr = perfil.unidade.cpr

                    # --------------------------------------------------
                    # GESTOR CPR
                    # --------------------------------------------------

                    elif perfil.perfil == "CPR":

                        novo_cpr = perfil.cpr

                        unidade_id = request.POST.get(
                            "unidade"
                        )

                        if not unidade_id:

                            form.add_error(
                                None,
                                "Selecione a Unidade."
                            )

                            return render(
                                request,
                                "gestao/cadastrar_usuario.html",
                                {
                                    "form": form,
                                    "unidade": unidade,
                                    "perfil": perfil,
                                    "unidades": Unidade.objects.filter(
                                        cpr=perfil.cpr,
                                        ativo=True
                                    ).order_by("sigla"),
                                }
                            )

                        nova_unidade = get_object_or_404(
                            Unidade,
                            id=unidade_id,
                            cpr=perfil.cpr,
                            ativo=True
                        )

                    # --------------------------------------------------
                    # GESTOR COPPM
                    # --------------------------------------------------

                    elif perfil.perfil == "COPPM":

                        unidade_id = request.POST.get(
                            "unidade"
                        )

                        if unidade_id:

                            nova_unidade = get_object_or_404(
                                Unidade,
                                id=unidade_id,
                                ativo=True
                            )

                            novo_cpr = nova_unidade.cpr

                        else:

                            cpr_id = request.POST.get(
                                "cpr"
                            )

                            if cpr_id:

                                novo_cpr = get_object_or_404(
                                    CPR,
                                    id=cpr_id,
                                    ativo=True
                                )

                    # ======================================
                    # CRIA USUÁRIO DJANGO
                    # ======================================

                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=senha,
                        first_name=nome,
                    )

                    # ======================================
                    # CRIA PERFIL SIEV
                    # ======================================

                    PerfilUsuario.objects.create(
                        usuario=user,
                        perfil="UNIDADE",
                        cpr=novo_cpr,
                        unidade=nova_unidade,
                        ativo=True,
                    )

                    # ======================================
                    # MATRÍCULA AUTORIZADA
                    # ======================================

                    MatriculaAutorizada.objects.create(
                        matricula=matricula,
                        nome=nome,
                        posto=posto,
                        unidade=nova_unidade,
                        ativo=True,
                    )

                messages.success(
                    request,
                    "Usuário cadastrado com sucesso."
                )

                return redirect(
                    "usuarios_unidade"
                )

            except Exception as erro:

                print(
                    "ERRO AO CADASTRAR USUÁRIO:",
                    repr(erro)
                )

                form.add_error(
                    None,
                    "Não foi possível cadastrar o usuário."
                )

    else:

        form = UsuarioGestaoForm()

    # ======================================================
    # DADOS PARA OS SELECTS
    # ======================================================

    if perfil.perfil == "COPPM":

        cprs = CPR.objects.filter(
            ativo=True
        ).order_by("sigla")

        unidades = Unidade.objects.filter(
            ativo=True
        ).select_related(
            "cpr"
        ).order_by("sigla")

    elif perfil.perfil == "CPR":

        cprs = CPR.objects.filter(
            id=perfil.cpr_id,
            ativo=True
        )

        unidades = Unidade.objects.filter(
            cpr=perfil.cpr,
            ativo=True
        ).order_by("sigla")

    else:

        cprs = CPR.objects.filter(
            id=perfil.unidade.cpr_id,
            ativo=True
        )

        unidades = Unidade.objects.filter(
            id=perfil.unidade_id,
            ativo=True
        )

    return render(
        request,
        "gestao/cadastrar_usuario.html",
        {
            "form": form,
            "unidade": unidade,
            "perfil": perfil,
            "cprs": cprs,
            "unidades": unidades,
        }
    )


# ==========================================================
# EDITAR USUÁRIO
# ==========================================================

@login_required
def editar_usuario_unidade(request, id):

    perfil = obter_perfil_gestor(request)

    if not perfil:
        messages.error(
            request,
            "Acesso não autorizado."
        )
        return redirect("painel_gestao")

    usuario_perfil = get_object_or_404(
        PerfilUsuario.objects.select_related(
            "usuario",
            "cpr",
            "unidade",
        ),
        id=id,
        ativo=True
    )

    # ======================================================
    # VERIFICAÇÃO DE HIERARQUIA
    # ======================================================

    if perfil.perfil == "UNIDADE":

        if usuario_perfil.unidade_id != perfil.unidade_id:

            messages.error(
                request,
                "Você não possui acesso a este usuário."
            )

            return redirect(
                "usuarios_unidade"
            )

    elif perfil.perfil == "CPR":

        if usuario_perfil.cpr_id != perfil.cpr_id:

            messages.error(
                request,
                "Você não possui acesso a este usuário."
            )

            return redirect(
                "usuarios_unidade"
            )

    elif perfil.perfil != "COPPM":

        messages.error(
            request,
            "Você não possui permissão."
        )

        return redirect(
            "painel_gestao"
        )

    usuario = usuario_perfil.usuario

    if request.method == "POST":

        nome = request.POST.get(
            "nome",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        username = request.POST.get(
            "username",
            ""
        ).strip()

        if not nome or not username:

            messages.error(
                request,
                "Nome e usuário são obrigatórios."
            )

            return redirect(
                "editar_usuario_unidade",
                id=id
            )

        # Verifica username duplicado
        if User.objects.filter(
            username=username
        ).exclude(
            id=usuario.id
        ).exists():

            messages.error(
                request,
                "Este nome de usuário já está sendo utilizado."
            )

            return redirect(
                "editar_usuario_unidade",
                id=id
            )

        usuario.username = username
        usuario.email = email

        partes_nome = nome.split()

        usuario.first_name = partes_nome[0]

        if len(partes_nome) > 1:
            usuario.last_name = " ".join(
                partes_nome[1:]
            )
        else:
            usuario.last_name = ""

        usuario.save()

        messages.success(
            request,
            "Usuário atualizado com sucesso."
        )

        return redirect(
            "usuarios_unidade"
        )

    return render(
        request,
        "gestao/editar_usuario.html",
        {
            "perfil": perfil,
            "usuario": usuario,
            "perfil_usuario": usuario_perfil,
        }
    )


# ==========================================================
# TROCAR SENHA
# ==========================================================

@login_required
def trocar_senha_usuario(request, id):

    perfil = obter_perfil_gestor(request)

    if not perfil:

        messages.error(
            request,
            "Acesso não autorizado."
        )

        return redirect("painel_gestao")

    usuario_perfil = get_object_or_404(
        PerfilUsuario.objects.select_related(
            "usuario",
            "cpr",
            "unidade",
        ),
        id=id,
        ativo=True
    )

    # ======================================================
    # SEGURANÇA
    # ======================================================

    if perfil.perfil == "UNIDADE":

        if usuario_perfil.unidade_id != perfil.unidade_id:

            messages.error(
                request,
                "Você não possui acesso a este usuário."
            )

            return redirect(
                "usuarios_unidade"
            )

    elif perfil.perfil == "CPR":

        if usuario_perfil.cpr_id != perfil.cpr_id:

            messages.error(
                request,
                "Você não possui acesso a este usuário."
            )

            return redirect(
                "usuarios_unidade"
            )

    elif perfil.perfil != "COPPM":

        messages.error(
            request,
            "Você não possui permissão."
        )

        return redirect(
            "painel_gestao"
        )

    if request.method == "POST":

        senha = request.POST.get(
            "senha",
            ""
        )

        senha_confirmacao = request.POST.get(
            "senha_confirmacao",
            ""
        )

        if len(senha) < 6:

            messages.error(
                request,
                "A senha deve possuir pelo menos 6 caracteres."
            )

            return redirect(
                "trocar_senha_usuario",
                id=id
            )

        if senha != senha_confirmacao:

            messages.error(
                request,
                "As senhas não conferem."
            )

            return redirect(
                "trocar_senha_usuario",
                id=id
            )

        usuario_perfil.usuario.set_password(
            senha
        )

        usuario_perfil.usuario.save()

        messages.success(
            request,
            "Senha alterada com sucesso."
        )

        return redirect(
            "usuarios_unidade"
        )

    return render(
        request,
        "gestao/trocar_senha.html",
        {
            "perfil": perfil,
            "perfil_usuario": usuario_perfil,
        }
    )


# ==========================================================
# DESATIVAR USUÁRIO
# ==========================================================

@login_required
def desativar_usuario_unidade(request, id):

    perfil = obter_perfil_gestor(request)

    if not perfil:

        messages.error(
            request,
            "Acesso não autorizado."
        )

        return redirect("painel_gestao")

    usuario_perfil = get_object_or_404(
        PerfilUsuario.objects.select_related(
            "usuario",
            "cpr",
            "unidade",
        ),
        id=id,
        ativo=True
    )

    # ======================================================
    # NÃO PODE DESATIVAR A PRÓPRIA CONTA
    # ======================================================

    if usuario_perfil.usuario_id == request.user.id:

        messages.error(
            request,
            "Você não pode desativar seu próprio usuário."
        )

        return redirect(
            "usuarios_unidade"
        )

    # ======================================================
    # SEGURANÇA
    # ======================================================

    if perfil.perfil == "UNIDADE":

        if usuario_perfil.unidade_id != perfil.unidade_id:

            messages.error(
                request,
                "Você não possui acesso a este usuário."
            )

            return redirect(
                "usuarios_unidade"
            )

    elif perfil.perfil == "CPR":

        if usuario_perfil.cpr_id != perfil.cpr_id:

            messages.error(
                request,
                "Você não possui acesso a este usuário."
            )

            return redirect(
                "usuarios_unidade"
            )

    elif perfil.perfil != "COPPM":

        messages.error(
            request,
            "Você não possui permissão."
        )

        return redirect(
            "painel_gestao"
        )

    # ======================================================
    # DESATIVA PERFIL
    # ======================================================

    usuario_perfil.ativo = False
    usuario_perfil.save()

    # Bloqueia também o login Django
    usuario_perfil.usuario.is_active = False
    usuario_perfil.usuario.save()

    # Se houver matrícula vinculada, também desativa
    MatriculaAutorizada.objects.filter(
        unidade=usuario_perfil.unidade,
        ativo=True
    ).filter(
        nome=usuario_perfil.usuario.get_full_name()
    ).update(
        ativo=False
    )

    messages.success(
        request,
        "Usuário desativado com sucesso."
    )

    return redirect(
        "usuarios_unidade"
    )
# ==================================================
# FUNÇÃO DE APROVAÇÕES
# ==================================================

@login_required
def aprovacoes(request):

    perfil = getattr(
        request.user,
        "perfil_siev",
        None
    )

    # ==================================================
    # DESENVOLVEDOR / ADMINISTRADOR
    # ==================================================

    if request.user.is_superuser or request.user.is_staff:

        solicitacoes = Solicitacao.objects.all()

    # ==================================================
    # SEM PERFIL
    # ==================================================

    elif not perfil:

        messages.error(
            request,
            "Usuário sem perfil institucional."
        )

        return redirect("login_gestao")

    # ==================================================
    # PERFIL INATIVO
    # ==================================================

    elif not perfil.ativo:

        messages.error(
            request,
            "Seu perfil institucional está inativo."
        )

        return redirect("logout_gestao")

    # ==================================================
    # COPPM
    # ==================================================

    elif perfil.perfil == "COPPM":

        solicitacoes = Solicitacao.objects.all()

    # ==================================================
    # CPR
    # ==================================================

    elif perfil.perfil == "CPR":

        solicitacoes = Solicitacao.objects.filter(
            unidade__cpr=perfil.cpr
        )

    # ==================================================
    # UNIDADE
    # ==================================================

    elif perfil.perfil == "UNIDADE":

        solicitacoes = Solicitacao.objects.filter(
            unidade=perfil.unidade
        )

    else:

        messages.error(
            request,
            "Perfil institucional inválido."
        )

        return redirect("logout_gestao")

    solicitacoes = solicitacoes.select_related(
        "unidade",
        "municipio",
        "tipo_evento"
    ).order_by(
        "data_evento",
        "hora_inicio"
    )

    return render(
        request,
        "gestao/aprovacoes.html",
        {
            "solicitacoes": solicitacoes,
            "perfil": perfil,
        }
    )
# ==========================================================
# APROVAR SOLICITAÇÃO
# ==========================================================

@login_required
def aprovar_solicitacao(request, id):

    if request.method != "POST":
        return redirect("aprovacoes")

    solicitacao = get_object_or_404(
        Solicitacao,
        id=id
    )

    # ------------------------------------------
    # ALTERA STATUS
    # ------------------------------------------

    solicitacao.status = "APROVADA"
    solicitacao.data_aprovacao = timezone.now()

    solicitacao.aprovado_por = (
        request.user.get_full_name()
        or request.user.username
    )

    solicitacao.save(
        update_fields=[
            "status",
            "data_aprovacao",
            "aprovado_por",
            "atualizado_em",
        ]
    )

    # ------------------------------------------
    # HISTÓRICO
    # ------------------------------------------

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        status="APROVADA",
        observacao="Solicitação aprovada pela unidade responsável.",
    )

    messages.success(
        request,
        f"Solicitação {solicitacao.protocolo} aprovada com sucesso."
    )

    return redirect("aprovacoes")

# ==========================================================
# SOLICITAR CORREÇÃO
# ==========================================================

@login_required
def solicitar_correcao_gestao(request, id):

    solicitacao = get_object_or_404(
        Solicitacao,
        id=id
    )

    if request.method == "POST":

        motivo = request.POST.get(
            "motivo_correcao",
            ""
        ).strip()

        if not motivo:

            messages.error(
                request,
                "Informe o motivo da correção."
            )

            return redirect(
                "aprovacoes"
            )

        # ==================================================
        # GUARDA O MOTIVO
        # ==================================================

        solicitacao.motivo_correcao = motivo

        # ==================================================
        # DEVOLVE PARA CORREÇÃO
        #
        # IMPORTANTE:
        # data_evento NÃO é alterada.
        # ==================================================

        solicitacao.status = "CORRECAO"

        solicitacao.save(
            update_fields=[
                "status",
                "motivo_correcao",
            ]
        )

        # ==================================================
        # HISTÓRICO
        # ==================================================

        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            status="CORRECAO",
            observacao=motivo,
        )

        # ==================================================
        # E-MAIL AO SOLICITANTE
        # ==================================================

        mensagem = f"""
Olá {solicitacao.solicitante},

Sua solicitação necessita de correção.

Motivo informado:

{motivo}

Após realizar as correções,
acesse novamente o SiEv para reenviar a solicitação.

Protocolo:
{solicitacao.protocolo}

Se preferir, compareça à sede da 95ª CIPM
para regularizar as pendências.

Após a regularização, uma nova análise será realizada.

Atenciosamente,

Seção de Planejamento Operacional
"""

        send_mail(
            subject="Pendência na Solicitação de Ordem de Policiamento",
            message=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[solicitacao.email],
            fail_silently=False,
        )

        messages.success(
            request,
            "Solicitante notificado por e-mail."
        )

        return redirect(
            "aprovacoes"
        )

    return render(
        request,
        "solicitacoes/solicitar_correcao.html",
        {
            "solicitacao": solicitacao
        }
    )
    # ------------------------------------------
    # HISTÓRICO
    # ------------------------------------------

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        status="CORRECAO",
        observacao=motivo,
    )

    messages.success(
        request,
        f"Solicitação {solicitacao.protocolo} enviada para correção."
    )

    return redirect("aprovacoes")


# ==================================================
# FUNÇÃO DE TRANSFERÊNCIA
# ==================================================


@login_required
def transferir_solicitacao(request, id):

    solicitacao = get_object_or_404(
        Solicitacao,
        id=id
    )

    perfil = getattr(
        request.user,
        "perfil_siev",
        None
    )

    # ==================================================
    # PERMISSÃO
    # ==================================================

    if not (
        request.user.is_superuser
        or request.user.is_staff
        or (
            perfil
            and perfil.ativo
            and perfil.perfil in [
                "COPPM",
                "CPR",
                "UNIDADE",
            ]
        )
    ):

        messages.error(
            request,
            "Você não possui permissão para transferir solicitações."
        )

        return redirect("aprovacoes")

    # ==================================================
    # VERIFICA SE A UNIDADE ATUAL PERTENCE AO USUÁRIO
    # ==================================================

    if (
        perfil
        and perfil.perfil == "UNIDADE"
        and solicitacao.unidade_id != perfil.unidade_id
    ):

        messages.error(
            request,
            "Esta solicitação não pertence à sua unidade."
        )

        return redirect("aprovacoes")

    # ==================================================
    # CPR
    # ==================================================

    if (
        perfil
        and perfil.perfil == "CPR"
        and solicitacao.unidade.cpr_id != perfil.cpr_id
    ):

        messages.error(
            request,
            "Esta solicitação não pertence ao seu CPR."
        )

        return redirect("aprovacoes")

    # ==================================================
    # UNIDADES DISPONÍVEIS
    # ==================================================

    unidades = Unidade.objects.filter(
        ativo=True
    ).exclude(
        id=solicitacao.unidade_id
    ).order_by(
        "nome"
    )

    # ==================================================
    # POST
    # ==================================================

    if request.method == "POST":

        unidade_id = request.POST.get(
            "unidade_destino"
        )

        motivo = request.POST.get(
            "motivo",
            ""
        ).strip()

        if not unidade_id:

            messages.error(
                request,
                "Selecione a unidade de destino."
            )

            return render(
                request,
                "gestao/transferir_solicitacao.html",
                {
                    "solicitacao": solicitacao,
                    "unidades": unidades,
                }
            )

        unidade_destino = get_object_or_404(
            Unidade,
            id=unidade_id,
            ativo=True
        )

        # ==================================================
        # NÃO PERMITIR MESMA UNIDADE
        # ==================================================

        if unidade_destino.id == solicitacao.unidade_id:

            messages.error(
                request,
                "A unidade de destino deve ser diferente da unidade atual."
            )

            return render(
                request,
                "gestao/transferir_solicitacao.html",
                {
                    "solicitacao": solicitacao,
                    "unidades": unidades,
                }
            )

        # ==================================================
        # TRANSFERÊNCIA
        # ==================================================

        with transaction.atomic():

            unidade_origem = solicitacao.unidade

            TransferenciaSolicitacao.objects.create(
                solicitacao=solicitacao,
                unidade_origem=unidade_origem,
                unidade_destino=unidade_destino,
                usuario=request.user,
                motivo=motivo,
            )

            solicitacao.unidade = unidade_destino

            solicitacao.origem = "TRANSFERIDA"

            solicitacao.save(
                update_fields=[
                    "unidade",
                    "origem",
                ]
            )

        messages.success(
            request,
            (
                f"Solicitação {solicitacao.protocolo} "
                f"transferida para {unidade_destino}."
            )
        )

        return redirect(
            "aprovacoes"
        )

    return render(
        request,
        "gestao/transferir_solicitacao.html",
        {
            "solicitacao": solicitacao,
            "unidades": unidades,
        }
    )