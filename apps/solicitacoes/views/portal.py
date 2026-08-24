# apps/solicitacoes/views/portal.py
from ..models import Solicitacao, PerfilUsuario
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from apps.solicitacoes.models import (
    Solicitacao,
    DocumentoSolicitacao,
    TipoDocumento,
    Municipio,
    TipoEvento,
    MatriculaAutorizada,
    Unidade,
)


from apps.solicitacoes.forms import SolicitacaoForm


# ==========================================================
# PORTAL PÚBLICO
# ==========================================================

def portal(request):
    """
    Página inicial do Portal SiEv.
    """

    return render(
        request,
        "portal/index.html",
        {
            "titulo": "Sistema Inteligente de Eventos",
        },
    )


# ==========================================================
# NOVA SOLICITAÇÃO
# ==========================================================

def nova_solicitacao(request):
    """
    Exibe o formulário de nova solicitação.
    """

    if request.method == "POST":
        return salvar_solicitacao(request)

    form = SolicitacaoForm()

    context = {
        "titulo": "Nova Solicitação",
        "form": form,
        "municipios": Municipio.objects.all().order_by("nome"),
        "tipos_evento": TipoEvento.objects.all().order_by("nome"),
    }

    return render(
        request,
        "portal/nova~].html",
        context,
    )


# ==========================================================
# SALVAR SOLICITAÇÃO
# ==========================================================

@transaction.atomic
def salvar_solicitacao(request):

    form = SolicitacaoForm(
        request.POST,
        request.FILES
    )

    if not form.is_valid():

        messages.error(
            request,
            "Existem campos obrigatórios não preenchidos."
        )

        return render(
            request,
            "portal/nova.html",
            {
                "form": form,
                "municipios": Municipio.objects.all().order_by("nome"),
                "tipos_evento": TipoEvento.objects.all().order_by("nome"),
            },
        )

    solicitacao = form.save(commit=False)

    solicitacao.data_cadastro = timezone.now()
    solicitacao.status = "PROTOCOLO"

    solicitacao.save()
    oficio = request.FILES.get("oficio_comandante")

    if oficio:
    
        tipo = TipoDocumento.objects.get(codigo="OFICIO_COMANDANTE")
    
        DocumentoSolicitacao.objects.create(
                solicitacao=solicitacao,
                tipo_documento=tipo,
                arquivo=oficio,
            )  
    # =====================================================
    # DOCUMENTOS COMPLEMENTARES
    # =====================================================

    tipos = request.POST.getlist("tipo_documento")
    descricoes = request.POST.getlist("descricao_documento")
    arquivos = request.FILES.getlist("documentos")

    for indice, arquivo in enumerate(arquivos):

        tipo = tipos[indice]

        if tipo == "OUTRO":
            nome = descricoes[indice]
        else:
            nome = tipo

        DocumentoSolicitacao.objects.create(
            solicitacao=solicitacao,
            nome=nome,
            arquivo=arquivo,
        )

    enviar_email_confirmacao(
        solicitacao
    )

    messages.success(
        request,
        "Solicitação cadastrada com sucesso."
    )

    return redirect(
        "protocolo_gerado",
        protocolo=solicitacao.protocolo
    )
# ==========================================================
# PROTOCOLO GERADO
# ==========================================================

def protocolo_gerado(request, protocolo):
    """
    Exibe a confirmação da solicitação enviada.
    """

    solicitacao = get_object_or_404(
        Solicitacao,
        protocolo=protocolo
    )

    context = {
        "titulo": "Solicitação Enviada",
        "solicitacao": solicitacao,
    }

    return render(
        request,
        "portal/protocolo_gerado.html",
        context,
    )


# ==========================================================
# CONSULTAR PROTOCOLO
# ==========================================================

def consultar_protocolo(request):
    """
    Consulta pública de protocolo.
    """

    protocolo = request.GET.get("protocolo", "").strip()

    solicitacao = None
    erro = None

    if protocolo:

        solicitacao = (
            Solicitacao.objects
            .filter(
                protocolo__iexact=protocolo
            )
            .first()
        )

        if not solicitacao:
            erro = "Protocolo não localizado."

    return render(
        request,
        "solicitacoes/consultar.html",
        {
            "solicitacao": solicitacao,
            "erro": erro,
            "protocolo_pesquisado": protocolo,
        }
    )

# ==========================================================
# ACOMPANHAR SOLICITAÇÃO
# ==========================================================

def acompanhar_solicitacao(request, protocolo):
    """
    Exibe todas as informações da solicitação.
    """

    solicitacao = get_object_or_404(
        Solicitacao,
        protocolo=protocolo
    )

    documentos = DocumentoSolicitacao.objects.filter(
        solicitacao=solicitacao
    )

    context = {

        "titulo": "Acompanhamento",

        "solicitacao": solicitacao,

        "documentos": documentos,

    }

    return render(
        request,
        "portal/acompanhar.html",
        context,
    )


# ==========================================================
# DOCUMENTOS
# ==========================================================

def upload_documentos(request, solicitacao):
    """
    Salva todos os documentos enviados.
    """

    arquivos = request.FILES.getlist("documentos")

    for arquivo in arquivos:

        DocumentoSolicitacao.objects.create(

            solicitacao=solicitacao,

            arquivo=arquivo,

            nome=arquivo.name,

        )


# ==========================================================
# EMAIL
# ==========================================================

def enviar_email_confirmacao(solicitacao):
    """
    Envia e-mail automático ao solicitante.
    """

    if not solicitacao.email:
        return

    assunto = "Solicitação Recebida - SiEv"

    mensagem = f"""
Prezado(a),

Sua solicitação foi recebida com sucesso.

PROTOCOLO:
{solicitacao.protocolo}

Acompanhe pela internet utilizando este número.

PMBA
Sistema Inteligente de Eventos
"""

    send_mail(

        assunto,

        mensagem,

        settings.DEFAULT_FROM_EMAIL,

        [solicitacao.email],

        fail_silently=True,

    )


# ==========================================================
# DOWNLOAD DO COMPROVANTE
# ==========================================================

def download_comprovante(request, protocolo):
    """
    Futuramente irá gerar o comprovante em PDF.
    """

    solicitacao = get_object_or_404(
        Solicitacao,
        protocolo=protocolo
    )

    response = HttpResponse(
        content_type="text/plain"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="protocolo_{protocolo}.txt"'
    )

    response.write(
        f"""
PROTOCOLO

{solicitacao.protocolo}

SOLICITANTE

{solicitacao.nome_solicitante}

EVENTO

{solicitacao.nome_evento}

STATUS

{solicitacao.status}
"""
    )

    return response




def eventos_dia(request):

    # ==========================================================
    # ACESSO INICIAL
    # ==========================================================

    if request.method == "GET":

        return render(
            request,
            "solicitacoes/eventos_dia.html"
        )

    # ==========================================================
    # CONSULTA DA MATRÍCULA
    # ==========================================================

    matricula = (
        request.POST.get("matricula", "")
        .strip()
    )

    if not matricula:

        return render(
            request,
            "solicitacoes/eventos_dia.html",
            {
                "erro": "Informe sua matrícula."
            }
        )

    # ==========================================================
    # LOCALIZA MATRÍCULA AUTORIZADA
    # ==========================================================

    matricula_autorizada = (
        MatriculaAutorizada.objects
        .filter(
            matricula=matricula,
            ativo=True
        )
        .first()
    )

    if not matricula_autorizada:

        return render(
            request,
            "solicitacoes/eventos_dia.html",
            {
                "erro": "Matrícula não autorizada."
            }
        )

    # ==========================================================
    # LOCALIZA A UNIDADE DA MATRÍCULA
    # ==========================================================

    unidade = (
        Unidade.objects
        .filter(
            sigla=matricula_autorizada.unidade,
            ativo=True
        )
        .select_related("cpr")
        .first()
    )

    if not unidade:

        return render(
            request,
            "solicitacoes/eventos_dia.html",
            {
                "erro": (
                    "A matrícula está cadastrada, "
                    "mas a unidade vinculada não foi localizada."
                )
            }
        )

    # ==========================================================
    # DATA DE HOJE
    # ==========================================================

    hoje = timezone.localdate()

    # ==========================================================
    # EVENTOS APROVADOS DA UNIDADE
    # ==========================================================

    eventos = (
        Solicitacao.objects
        .filter(
            data_evento=hoje,
            status="APROVADO",
            unidade=unidade
        )
        .order_by(
            "hora_inicio",
            "nome_evento"
        )
    )

    # ==========================================================
    # MOSTRA RESULTADO
    # ==========================================================

    return render(
        request,
        "solicitacoes/eventos_dia_resultado.html",
        {
            "eventos": eventos,
            "matricula": matricula,
            "matricula_autorizada": matricula_autorizada,
            "unidade": unidade,
            "data": hoje,
        }
    )


def eventos_dia_resultado(request):
    """
    Exibe os eventos de hoje conforme o perfil
    e a unidade/CPR do usuário.
    """

    matricula = request.session.get(
        "eventos_matricula"
    )

    if not matricula:
        return redirect(
            "eventos_dia"
        )

    perfil = (
        PerfilUsuario.objects
        .select_related(
            "usuario",
            "unidade",
            "cpr"
        )
        .filter(
            matricula=matricula,
            ativo=True
        )
        .first()
    )

    if not perfil:
        request.session.pop(
            "eventos_matricula",
            None
        )

        messages.error(
            request,
            "Matrícula não autorizada."
        )

        return redirect(
            "eventos_dia"
        )

    hoje = timezone.localdate()

    eventos = Solicitacao.objects.filter(
        data_evento=hoje
    ).select_related(
        "municipio",
        "unidade",
        "bairro"
    ).order_by(
        "hora_inicio",
        "nome_evento"
    )

    # ==========================================
    # GESTOR DE UNIDADE
    # ==========================================

    if perfil.perfil == "UNIDADE":

        eventos = eventos.filter(
            unidade=perfil.unidade
        )

    # ==========================================
    # GESTOR DE CPR
    # ==========================================

    elif perfil.perfil == "CPR":

        eventos = eventos.filter(
            unidade__cpr=perfil.cpr
        )

    # ==========================================
    # COPPM
    # ==========================================

    elif perfil.perfil == "COPPM":

        pass

    else:

        eventos = eventos.none()

    return render(
        request,
        "solicitacoes/eventos_dia_resultado.html",
        {
            "eventos": eventos,
            "perfil": perfil,
            "data_eventos": hoje,
        }
    )