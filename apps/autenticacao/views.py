from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
import os   
from reportlab.pdfgen import canvas
from .models import Solicitacao
from .forms import SolicitacaoForm
from django.http import HttpResponse
import traceback
from django.shortcuts import render
from django.shortcuts import render


def nova_solicitacao(request):

    if request.method == 'POST':
        print("ENTROU NA VIEW")
        

        form = SolicitacaoForm(request.POST, request.FILES)

        if form.is_valid():

            try:

                solicitacao = form.save(commit=False)
                solicitacao.status = 'PENDENTE'
                solicitacao.save()

                send_mail(
                    'Solicitação Recebida',
                    'Teste',
                    settings.DEFAULT_FROM_EMAIL,
                    [solicitacao.email],
                    fail_silently=False
                )

                return render(
                    request,
                    'solicitacoes/sucesso.html',
                    {'protocolo': solicitacao.protocolo}
                )

            except Exception as e:

                erro = traceback.format_exc()

                return HttpResponse(
                    f"<pre>{erro}</pre>"
                )

        else:

            return HttpResponse(
                str(form.errors)
            )

    form = SolicitacaoForm()

    return render(
        request,
        'solicitacoes/nova.html',
        {'form': form}
    )
   
def minhas_solicitacoes(request):
    return render(
        request,
        'solicitacoes/minhas_solicitacoes.html'
    )

# =====================================================
# HOME
# =====================================================
@login_required
def menu_gestao(request):

    return render(
        request,
        'gestao/menu.html'
    )
def home(request):

    return render(request, 'home.html')


# =====================================================
# NOVA SOLICITAÇÃO
# =====================================================

from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings

from .forms import SolicitacaoForm


def nova_solicitacao(request):

    if request.method == 'POST':

        print('=' * 50)
        print('ENTROU NO POST')
        print('=' * 50)

        form = SolicitacaoForm(
            request.POST,
            request.FILES
        )

        print('FORMULÁRIO RECEBIDO')

        if form.is_valid():

            print('FORMULÁRIO VÁLIDO')

            try:

                solicitacao = form.save(commit=False)

                solicitacao.status = 'PENDENTE'

                solicitacao.save()

                print(
                    f'SOLICITAÇÃO SALVA - PROTOCOLO: {solicitacao.protocolo}'
                )

                assunto = 'Solicitação de Evento Recebida'

                mensagem = f'''
Olá, {solicitacao.solicitante}!

Sua solicitação foi enviada com sucesso.

PROTOCOLO:
{solicitacao.protocolo}

EVENTO:
{solicitacao.nome_evento}

DATA:
{solicitacao.data_evento}

STATUS:
{solicitacao.status}

Guarde este protocolo para acompanhamento.

PMBA, Uma Força a Serviço do Cidadão!
                '''

                try:

                    send_mail(
                        assunto,
                        mensagem,
                        settings.DEFAULT_FROM_EMAIL,
                        [solicitacao.email],
                        fail_silently=True
                    )

                    print('EMAIL ENVIADO')

                except Exception as erro_email:

                    print(
                        f'ERRO AO ENVIAR EMAIL: {erro_email}'
                    )

                return render(
                    request,
                    'solicitacoes/sucesso.html',
                    {
                        'protocolo': solicitacao.protocolo
                    }
                )

            except Exception as erro:

                print('=' * 50)
                print('ERRO AO SALVAR SOLICITAÇÃO')
                print(str(erro))
                print(type(erro))
                print('=' * 50)

                raise

        else:

            print('=' * 50)
            print('FORMULÁRIO INVÁLIDO')
            print(form.errors)
            print(form.non_field_errors())
            print('=' * 50)

    else:

        form = SolicitacaoForm()

    return render(
        request,
        'solicitacoes/nova.html',
        {
            'form': form
        }
    )


# =====================================================
# MINHAS SOLICITAÇÕES
# =====================================================

def minhas_solicitacoes(request):

    protocolo = request.GET.get('protocolo')

    solicitacao = None
    erro = None

    if protocolo:

        try:
            solicitacao = Solicitacao.objects.get(
                protocolo=protocolo.upper()
            )

        except Solicitacao.DoesNotExist:
            erro = "Protocolo não encontrado."

    return render(
        request,
        'solicitacoes/minhas.html',
        {
            'solicitacao': solicitacao,
            'erro': erro
        }
    )


# =====================================================
# DASHBOARD OPERACIONAL
# =====================================================

@login_required
def dashboard_operacional(request):

    solicitacoes = Solicitacao.objects.all().order_by('-criado_em')

    total = solicitacoes.count()

    pendentes = solicitacoes.filter(
        status='PENDENTE'
    ).count()

    aprovadas = solicitacoes.filter(
        status='APROVADO'
    ).count()

    return render(
        request,
        'solicitacoes/dashboard.html',
        {
            'solicitacoes': solicitacoes,
            'total': total,
            'pendentes': pendentes,
            'aprovadas': aprovadas,
        }
    )


# =====================================================
# APROVAR SOLICITAÇÃO
# =====================================================

def aprovar_solicitacao(request, id):

    solicitacao = get_object_or_404(
        Solicitacao,
        id=id
    )

    solicitacao.status = 'APROVADO'

    solicitacao.data_assinatura = timezone.now()

    solicitacao.assinado_por = 'Administrador'

    solicitacao.save()

    # =================================================
    # EMAIL DE APROVAÇÃO
    # =================================================

    assunto = 'Solicitação Aprovada'

    mensagem = f'''
Olá, {solicitacao.solicitante}!

Sua solicitação foi APROVADA.

PROTOCOLO:
{solicitacao.protocolo}

EVENTO:
{solicitacao.nome_evento}

DATA:
{solicitacao.data_evento}

STATUS:
{solicitacao.status}

PMBA, Uma Força a serviço do cidadão!
    '''

    try:

        send_mail(
            assunto,
            mensagem,
            settings.DEFAULT_FROM_EMAIL,
            [solicitacao.email],
            fail_silently=True
        )

    except Exception as erro:

        print('ERRO AO ENVIAR EMAIL:', erro)

    return redirect('painel_gestao')


# =====================================================
# ALTERAR STATUS
# =====================================================

def alterar_status(request, id, status):

    solicitacao = get_object_or_404(
        Solicitacao,
        id=id
    )

    solicitacao.status = status.upper()

    solicitacao.save()

    return redirect('dashboard_operacional')


# =====================================================
# VERIFICAR AUTENTICIDADE
# =====================================================

def verificar_autenticidade(request, protocolo):

    solicitacao = Solicitacao.objects.filter(
        protocolo=protocolo
    ).first()

    return render(
        request,
        'solicitacoes/verificar.html',
        {
            'solicitacao': solicitacao
        }
    )


# =====================================================
# GERAR PDF
# =====================================================

def gerar_pdf(request, id):

    solicitacao = get_object_or_404(
        Solicitacao,
        id=id
    )

    response = HttpResponse(
        content_type='application/pdf'
    )

    response[
        'Content-Disposition'
    ] = f'inline; filename="solicitacao_{solicitacao.id}.pdf"'

    p = canvas.Canvas(response)

    y = 800

    p.setFont("Helvetica-Bold", 16)

    p.drawString(
        180,
        y,
        "SOLICITAÇÃO DE EVENTO"
    )

    y -= 50

    p.setFont("Helvetica", 12)

    dados = [

        f"Protocolo: {solicitacao.protocolo}",
        f"Solicitante: {solicitacao.solicitante}",
        f"CPF: {solicitacao.documento_pessoal}",
        f"Telefone: {solicitacao.telefone}",
        f"E-mail: {solicitacao.email}",
        f"Evento: {solicitacao.nome_evento}",
        f"Local: {solicitacao.local}",
        f"Data Evento: {solicitacao.data_evento}",
        f"Hora Início: {solicitacao.hora_inicio}",
        f"Hora Fim: {solicitacao.hora_fim}",
        f"Público Estimado: {solicitacao.publico_estimado}",
        f"Status: {solicitacao.status}",
        f"Criado em: {solicitacao.criado_em}",

    ]

    for item in dados:

        p.drawString(70, y, item)

        y -= 25

    y -= 20

    p.drawString(
        70,
        y,
        "Observações:"
    )

    y -= 25

    p.drawString(
        70,
        y,
        str(solicitacao.observacoes)
    )

    p.showPage()

    p.save()

    return response

def login_gestao(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user:
            login(request, user)
            return redirect('painel_gestao')

    return render(
        request,
        'gestao/login.html'
    )


def logout_gestao(request):

    logout(request)

    return redirect('home')

def consultar_protocolo(request):
    return render(
        request,
        'solicitacoes/consultar.html'
    )
    
# =====================================================
# PAINEL DA GESTÃO
# =====================================================

from django.contrib.auth.decorators import login_required

@login_required
def painel_gestao(request):

    return render(
        request,
        'gestao/painel.html'
    )
def home(request):
    return render(request, 'home.html')