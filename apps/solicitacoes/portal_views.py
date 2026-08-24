from .models import Municipio
from django.shortcuts import redirect
from apps.solicitacoes.models import Municipio
from django.http import JsonResponse
from .models import Unidade
from django.shortcuts import render, get_object_or_404, redirect
from .models import Solicitacao, MatriculaAutorizada
import os
import base64
from io import BytesIO
from datetime import date, timedelta
from pathlib import Path
import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import FileResponse, HttpResponse, Http404
from django.urls import reverse
from django.utils import timezone
from .models import Solicitacao
from .forms import SolicitacaoForm, SolicitacaoManualForm, CorrecaoSolicitacaoForm
import openpyxl
from django.contrib import messages
from .models import MatriculaAutorizada
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from apps.solicitacoes.models import (
    Solicitacao,
    Municipio,
    Bairro,
    Unidade,
    DocumentoSolicitacao,
    TipoDocumento,
)
# =====================================================
# COMANDOS REGIONAIS
# =====================================================

COMANDOS = [

    {"id": 1, "sigla": "CPRC-A", "nome": "Atlântico", "cidade": "Salvador"},

    {"id": 2, "sigla": "CPRC-BTS", "nome": "Baía de Todos os Santos", "cidade": "Salvador"},

    {"id": 3, "sigla": "CPRC-C", "nome": "Central", "cidade": "Salvador"},

    {"id": 4, "sigla": "CPR-L", "nome": "Leste", "cidade": "Feira de Santana"},

    {"id": 5, "sigla": "CPR-N", "nome": "Norte", "cidade": "Juazeiro"},

    {"id": 6, "sigla": "CPR-S", "nome": "Sul", "cidade": "Itabuna"},

    {"id": 7, "sigla": "CPR-O", "nome": "Oeste", "cidade": "Barreiras"},

    {"id": 8, "sigla": "CPR-SO", "nome": "Sudoeste", "cidade": "Vitória da Conquista"},

    {"id": 9, "sigla": "CPR-ES", "nome": "Extremo Sul", "cidade": "Teixeira de Freitas"},

    {"id": 10, "sigla": "CPR-Chp", "nome": "Chapada", "cidade": "Itaberaba"},

    {"id": 11, "sigla": "CPR-R", "nome": "Recôncavo", "cidade": "Santo Antônio de Jesus"},

    {"id": 12, "sigla": "CPR-MO", "nome": "Meio Oeste", "cidade": "Bom Jesus da Lapa"},

    {"id": 13, "sigla": "CPR-NE", "nome": "Nordeste", "cidade": "Ribeira do Pombal"},

    {"id": 14, "sigla": "CPR-LN", "nome": "Litoral Norte", "cidade": "Alagoinhas"},

    {"id": 15, "sigla": "CPR-CN", "nome": "Centro Norte", "cidade": "Irecê"},

    {"id": 16, "sigla": "CPR-MRC", "nome": "Médio Rio de Contas", "cidade": "Jequié"}

]


# =====================================================
# PORTAL
# =====================================================

def portal(request):

    contexto = {
        "comandos": COMANDOS
    }

    return render(
        request,
        "portal.html",
        contexto
    )


# =====================================================
# ENTRADA
# =====================================================



def selecionar_unidade(request):

    
    if request.method != "POST":
        return redirect("portal")

    municipio_id = request.POST.get("municipio")

    if not municipio_id:
        messages.error(request, "Selecione um município.")
        return redirect("portal")

    request.session["municipio_id"] = municipio_id

    return redirect("nova_solicitacao")

def listar_unidades(request, cpr_id):

    unidades = Unidade.objects.filter(
        cpr_id=cpr_id
    ).order_by("nome")

    dados = []

    for unidade in unidades:

        dados.append({

            "id": unidade.id,
            "nome": unidade.nome

        })

    return JsonResponse(dados, safe=False)


def lista_municipios(request):

    termo = request.GET.get("q", "")

    municipios = Municipio.objects.filter(
        nome__icontains=termo,
        ativo=True
    ).order_by("nome")[:20]

    return JsonResponse(
        list(
            municipios.values(
                "id",
                "nome"
            )
        ),
        safe=False
    )
    
def nova_solicitacao(request):

    # ==========================================================
    # MUNICÍPIO ESCOLHIDO ANTES DA SOLICITAÇÃO
    # ==========================================================

    municipio_id = request.GET.get("municipio")

    municipio = None

    if municipio_id:
        municipio = Municipio.objects.filter(
            id=municipio_id
        ).first()

    # ==========================================================
    # POST
    # ==========================================================
        municipio_id = request.GET.get("municipio")

        municipio = None

    if municipio_id:

        municipio = Municipio.objects.filter(
            id=municipio_id
        ).first()

    if not municipio:

        return redirect("/")
    if request.method == "POST":

        form = SolicitacaoForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            # ==================================================
            # INFORMAÇÕES GERADAS PELO FORMULÁRIO
            # ==================================================

            aviso_multiplas_datas = getattr(
                form,
                "aviso_multiplas_datas",
                False
            )

            datas_encontradas = getattr(
                form,
                "datas_encontradas_oficio",
                []
            )

            try:

                # ==============================================
                # SALVA A SOLICITAÇÃO
                # ==============================================

                solicitacao = form.save(commit=False)

                # ==================================================
                # MUNICÍPIO ESCOLHIDO ANTERIORMENTE
                # ==================================================

                solicitacao.municipio = municipio


                # ==================================================
                # DIRECIONAMENTO TERRITORIAL
                # ==================================================

                if municipio:

                    unidade = municipio.unidade_responsavel

                    if unidade:

                        # Município possui uma única unidade responsável
                        solicitacao.unidade = unidade

                        # Busca o bairro padrão Centro
                        bairro_centro = Bairro.objects.filter(
                            municipio=municipio,
                            nome__iexact="Centro",
                            ativo=True
                        ).first()

                        if bairro_centro:

                            solicitacao.bairro = bairro_centro


                # ==================================================
                # STATUS INICIAL
                # ==================================================

                solicitacao.status = "PENDENTE"


                # ==================================================
                # SALVA
                # ==================================================

                solicitacao.save()

                # ==================================================
                # DOCUMENTOS COMPLEMENTARES
                # ==================================================

                tipos = request.POST.getlist(
                    "tipo_documento"
                )

                descricoes = request.POST.getlist(
                    "descricao_documento"
                )

                arquivos = request.FILES.getlist(
                    "documentos"
                )

                for i, arquivo in enumerate(arquivos):

                    if not arquivo:
                        continue

                    tipo_nome = (
                        tipos[i]
                        if i < len(tipos)
                        else ""
                    )

                    descricao = (
                        descricoes[i]
                        if i < len(descricoes)
                        else ""
                    )

                    if not tipo_nome:
                        continue

                    tipo_documento = (
                        TipoDocumento.objects.filter(
                            nome=tipo_nome,
                            ativo=True
                        ).first()
                    )

                    if not tipo_documento:
                        continue

                    DocumentoSolicitacao.objects.create(
                        solicitacao=solicitacao,
                        tipo_documento=tipo_documento,
                        descricao=descricao,
                        arquivo=arquivo
                    )

                # ==================================================
                # EMAIL DE CONFIRMAÇÃO
                #
                # FICA FORA DO FOR!
                # ==================================================

                assunto = (
                    "Solicitação de Evento Recebida"
                )

                mensagem = f"""
Olá, {solicitacao.solicitante}!

Sua solicitação foi recebida com sucesso.

PROTOCOLO:
{solicitacao.protocolo}

EVENTO:
{solicitacao.nome_evento}

DATA:
{solicitacao.data_evento.strftime("%d/%m/%Y")}

STATUS:
{solicitacao.get_status_display()}

Guarde este protocolo para futuras consultas.

PMBA - Uma força a serviço do cidadão.
"""

                try:

                    send_mail(
                        assunto,
                        mensagem,
                        settings.DEFAULT_FROM_EMAIL,
                        [solicitacao.email],
                        fail_silently=False
                    )

                except Exception as erro_email:

                    print(
                        "ERRO AO ENVIAR EMAIL:",
                        repr(erro_email)
                    )

                # ==================================================
                # SUCESSO
                # ==================================================

                return render(
                    request,
                    "solicitacoes/sucesso.html",
                    {
                        "protocolo": solicitacao.protocolo,

                        "aviso_multiplas_datas":
                            aviso_multiplas_datas,

                        "datas_encontradas":
                            datas_encontradas,
                    }
                )

            except Exception as erro:

                print(
                    "ERRO AO SALVAR SOLICITAÇÃO:",
                    repr(erro)
                )

                form.add_error(
                    None,
                    "Ocorreu um erro ao salvar a "
                    "solicitação. Tente novamente."
                )

    # ==========================================================
    # GET
    # ==========================================================

    else:

        form = SolicitacaoForm()

    # ==========================================================
    # FORMULÁRIO
    # ==========================================================

    return render(
        request,
        "solicitacoes/nova.html",
        {
            "form": form,
            "municipio": municipio,
        }
    )
# =====================================================
# CONSULTAR PROTOCOLO
# =====================================================

def consultar_protocolo(request):

    protocolo = request.GET.get("protocolo")

    solicitacao = None
    erro = None

    eventos_hoje = Solicitacao.objects.filter(
        data_evento=date.today()
    ).order_by(
        "hora_inicio",
        "nome_evento"
    )

    if protocolo:

        solicitacao = Solicitacao.objects.filter(
            protocolo=protocolo.upper()
        ).first()

        if not solicitacao:
            erro = "Protocolo não encontrado."

    return render(
        request,
        "solicitacoes/consultar.html",
        {
            "solicitacao": solicitacao,
            "erro": erro,
            "eventos_hoje": eventos_hoje,
        }
    )
    

# =====================================================
# CORREÇÃO DE SOLICITAÇÃO
# =====================================================

def corrigir_solicitacao(request, protocolo):

    solicitacao = get_object_or_404(
        Solicitacao,
        protocolo=protocolo
    )

    # ======================================================
    # SÓ PERMITE CORREÇÃO QUANDO ESTIVER EM CORRECAO
    # ======================================================

    if solicitacao.status != "CORRECAO":

        messages.error(
            request,
            "Esta solicitação não está disponível para correção."
        )

        return redirect(
            f"/consultar/?protocolo={solicitacao.protocolo}"
        )

    # ======================================================
    # POST
    # ======================================================

    if request.method == "POST":

        form = CorrecaoSolicitacaoForm(
            request.POST,
            request.FILES,
            instance=solicitacao
        )

        if form.is_valid():

            # ==============================================
            # SALVA AS CORREÇÕES
            # ==============================================

            obj = form.save(commit=False)

            # ==============================================
            # GARANTE O MESMO PROTOCOLO
            # ==============================================

            obj.protocolo = solicitacao.protocolo

            # ==============================================
            # GARANTE A DATA ORIGINAL
            #
            # NÃO CALCULA.
            # NÃO CONVERTE.
            # NÃO VALIDA.
            #
            # Apenas mantém o valor que já estava no banco.
            # ==============================================

            obj.data_evento = solicitacao.data_evento

            # ==============================================
            # VOLTA PARA ANÁLISE
            # ==============================================

            obj.status = "PENDENTE"

            obj.save()

            # ==============================================
            # MENSAGEM
            # ==============================================

            messages.success(
                request,
                "Correções enviadas com sucesso. "
                "Sua solicitação será analisada novamente."
            )

            return redirect(
                f"/consultar/?protocolo={obj.protocolo}"
            )

    # ======================================================
    # GET
    # ======================================================

    else:

        form = CorrecaoSolicitacaoForm(
            instance=solicitacao
        )

    # ======================================================
    # FORMULÁRIO DE CORREÇÃO
    # ======================================================

    return render(
        request,
        "solicitacoes/nova.html",
        {
            "form": form,
            "solicitacao": solicitacao,
            "modo_correcao": True,
        }
    )

    # ==================================================
    # POST - REENVIO
    # ==================================================

    if request.method == "POST":

        form = SolicitacaoForm(
            request.POST,
            request.FILES,
            instance=solicitacao
        )

        if form.is_valid():

            # ------------------------------------------
            # PRESERVA A DATA ORIGINAL
            # ------------------------------------------

            data_evento_original = solicitacao.data_evento

            solicitacao = form.save(
                commit=False
            )

            solicitacao.data_evento = (
                data_evento_original
            )

            solicitacao.status = "ENVIADA"

            solicitacao.save()

            # ------------------------------------------
            # HISTÓRICO
            # ------------------------------------------

            HistoricoSolicitacao.objects.create(
                solicitacao=solicitacao,
                usuario=None,
                status="ENVIADA",
                observacao=(
                    "Solicitação corrigida e "
                    "reenviada pelo solicitante."
                ),
            )

            # ------------------------------------------
            # E-MAIL DE CONFIRMAÇÃO
            # ------------------------------------------

            mensagem = f"""
Olá {solicitacao.solicitante},

Sua solicitação foi corrigida e reenviada
para análise.

Protocolo:
{solicitacao.protocolo}

Evento:
{solicitacao.nome_evento}

Data:
{solicitacao.data_evento.strftime("%d/%m/%Y")}

O pedido será novamente analisado pela
unidade responsável.

Atenciosamente,

Seção de Planejamento Operacional
"""

            try:

                send_mail(
                    subject=(
                        "Solicitação corrigida e "
                        "reenviada - SiEv"
                    ),
                    message=mensagem,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[
                        solicitacao.email
                    ],
                    fail_silently=False,
                )

            except Exception as erro_email:

                print(
                    "ERRO AO ENVIAR EMAIL:",
                    repr(erro_email)
                )

            messages.success(
                request,
                "Solicitação corrigida e reenviada com sucesso."
            )

            return redirect(
                "consultar"
            )

    else:

        form = SolicitacaoForm(
            instance=solicitacao
        )

    return render(
        request,
        "solicitacoes/corrigir.html",
        {
            "form": form,
            "solicitacao": solicitacao,
        }
    )
    
@login_required
def agenda_gestao(request):

    hoje = date.today()

    # -------------------------------------------------
    # SOMENTE EVENTOS ANTERIORES A HOJE
    # -------------------------------------------------

    eventos = Solicitacao.objects.filter(
        status__in=["APROVADO", "CORRECAO"],
        data_evento__lt=hoje
    )

    # -------------------------------------------------
    # FILTRO POR DIA
    # Exemplo: ?dia=2026-08-10
    # -------------------------------------------------

    dia = request.GET.get("dia")

    if dia:
        try:
            data_filtro = date.fromisoformat(dia)

            eventos = eventos.filter(
                data_evento=data_filtro
            )

        except ValueError:
            pass

    # -------------------------------------------------
    # FILTRO POR MÊS
    # Exemplo: ?mes=8
    # -------------------------------------------------

    mes = request.GET.get("mes")

    if mes:
        try:
            eventos = eventos.filter(
                data_evento__month=int(mes)
            )

        except ValueError:
            pass

    # -------------------------------------------------
    # FILTRO POR ANO
    # Exemplo: ?ano=2026
    # -------------------------------------------------

    ano = request.GET.get("ano")

    if ano:
        try:
            eventos = eventos.filter(
                data_evento__year=int(ano)
            )

        except ValueError:
            pass

    # -------------------------------------------------
    # ORDENAÇÃO
    # -------------------------------------------------

    eventos = eventos.order_by(
        "-data_evento",
        "-hora_inicio"
    )

    # -------------------------------------------------
    # ANOS DISPONÍVEIS NO BANCO
    # -------------------------------------------------

    anos = (
        Solicitacao.objects
        .filter(
            status__in=["APROVADO", "CORRECAO"],
            data_evento__lt=hoje
        )
        .dates(
            "data_evento",
            "year",
            order="DESC"
        )
    )

    anos = [data.year for data in anos]

    return render(
        request,
        "gestao/agenda.html",
        {
            "eventos": eventos,
            "anos": anos,
            "filtro_dia": dia,
            "filtro_mes": mes,
            "filtro_ano": ano,
        }
    )
# =====================================================
# PRÓXIMOS EVENTOS
# =====================================================

@login_required
def proximos_eventos_gestao(request):

    hoje = date.today()

    eventos = Solicitacao.objects.filter(
        status__in=["APROVADO", "CORRECAO"],
        data_evento__gte=hoje
    ).order_by(
        "data_evento",
        "hora_inicio"
    )

    return render(
        request,
        "gestao/proximos_eventos.html",
        {
            "eventos": eventos,
        }
    )
@login_required
def listar_pendentes_opo(request):

    solicitacoes = Solicitacao.objects.filter(
        status="PENDENTE"
    ).order_by(
        "data_evento",
        "hora_inicio"
    )

    return render(
        request,
        "gestao/aprovacoes.html",
        {
            "solicitacoes": solicitacoes,
        }
    )