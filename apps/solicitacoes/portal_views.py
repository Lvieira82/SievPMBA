from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CorrecaoSolicitacaoForm, SolicitacaoForm
from .models import (
    DocumentoSolicitacao,
    Municipio,
    Solicitacao,
    TipoDocumento,
    Unidade,
)
from .territorio import (
    bairros_do_municipio,
    lista_bairros as lista_bairros_api,
    municipio_tem_multiplas_unidades,
    unidades_do_municipio,
    validar_direcionamento,
)


# =====================================================
# PORTAL PÚBLICO
# =====================================================

def portal(request):
    return render(request, "portal.html")


# =====================================================
# ENTRADA / MUNICÍPIO
# =====================================================

def selecionar_unidade(request):
    if request.method != "POST":
        return redirect("portal")

    municipio_id = request.POST.get("municipio")
    if not municipio_id:
        messages.error(request, "Selecione um município.")
        return redirect("portal")

    municipio = Municipio.objects.filter(id=municipio_id, ativo=True).first()
    if not municipio:
        messages.error(request, "Município inválido.")
        return redirect("portal")

    request.session["municipio_id"] = municipio.id
    return redirect("nova_solicitacao")


def listar_unidades(request, cpr_id):
    unidades = (
        Unidade.objects
        .filter(cpr_id=cpr_id, ativo=True)
        .order_by("nome")
    )

    return JsonResponse(
        [{"id": unidade.id, "nome": unidade.nome} for unidade in unidades],
        safe=False,
    )


def lista_municipios(request):
    termo = request.GET.get("q", "").strip()

    municipios = (
        Municipio.objects
        .filter(nome__icontains=termo, ativo=True)
        .order_by("nome")[:20]
    )

    dados = []
    for municipio in municipios:
        unidades = unidades_do_municipio(municipio)
        dados.append({
            "id": municipio.id,
            "nome": municipio.nome,
            "multiplas_unidades": unidades.count() > 1,
        })

    return JsonResponse(dados, safe=False)


def lista_bairros(request, municipio_id):
    return lista_bairros_api(request, municipio_id)


# =====================================================
# NOVA SOLICITAÇÃO
# =====================================================

def _configurar_bairro_form(form, municipio):
    if "bairro" not in form.fields:
        return False

    bairros = bairros_do_municipio(municipio)
    multiplas = municipio_tem_multiplas_unidades(municipio)

    form.fields["bairro"].queryset = bairros
    form.fields["bairro"].required = multiplas
    form.fields["bairro"].widget.attrs.update({
        "class": "form-select",
        "data-territorial": "true",
    })

    return multiplas


def _render_nova(request, form, municipio):
    multiplas = _configurar_bairro_form(form, municipio)

    return render(
        request,
        "solicitacoes/nova.html",
        {
            "form": form,
            "municipio": municipio,
            "multiplas_unidades": multiplas,
            "bairros": bairros_do_municipio(municipio),
        },
    )


def nova_solicitacao(request):
    municipio_id = request.GET.get("municipio") or request.session.get("municipio_id")

    municipio = Municipio.objects.filter(
        id=municipio_id,
        ativo=True,
    ).first()

    if not municipio:
        messages.error(request, "Selecione um município antes de continuar.")
        return redirect("portal")

    if request.method == "POST":
        form = SolicitacaoForm(request.POST, request.FILES)
        multiplas = _configurar_bairro_form(form, municipio)

        if form.is_valid():
            bairro = form.cleaned_data.get("bairro")

            try:
                unidade = validar_direcionamento(municipio, bairro)
            except Exception as erro:
                form.add_error("bairro", str(erro))
            else:
                if multiplas and not unidade:
                    form.add_error(
                        "bairro",
                        "O bairro selecionado ainda não possui uma unidade responsável cadastrada.",
                    )
                else:
                    solicitacao = form.save(commit=False)
                    solicitacao.municipio = municipio
                    solicitacao.unidade = unidade
                    solicitacao.status = "PENDENTE"
                    solicitacao.save()

                    _salvar_documentos(request, solicitacao)
                    _enviar_email_recebimento(solicitacao)

                    return render(
                        request,
                        "solicitacoes/sucesso.html",
                        {
                            "protocolo": solicitacao.protocolo,
                            "aviso_multiplas_datas": getattr(
                                form,
                                "aviso_multiplas_datas",
                                False,
                            ),
                            "datas_encontradas": getattr(
                                form,
                                "datas_encontradas_oficio",
                                [],
                            ),
                        },
                    )
    else:
        form = SolicitacaoForm()

    return _render_nova(request, form, municipio)


def _salvar_documentos(request, solicitacao):
    tipos = request.POST.getlist("tipo_documento")
    descricoes = request.POST.getlist("descricao_documento")
    arquivos = request.FILES.getlist("documentos")

    for indice, arquivo in enumerate(arquivos):
        if not arquivo:
            continue

        tipo_nome = tipos[indice] if indice < len(tipos) else ""
        descricao = descricoes[indice] if indice < len(descricoes) else ""

        if not tipo_nome:
            continue

        tipo_documento = TipoDocumento.objects.filter(
            nome=tipo_nome,
            ativo=True,
        ).first()

        if not tipo_documento:
            continue

        DocumentoSolicitacao.objects.create(
            solicitacao=solicitacao,
            tipo_documento=tipo_documento,
            descricao=descricao,
            arquivo=arquivo,
        )


def _enviar_email_recebimento(solicitacao):
    if not solicitacao.email:
        return

    mensagem = f"""
Olá, {solicitacao.solicitante}!

Sua solicitação foi recebida com sucesso.

PROTOCOLO:
{solicitacao.protocolo}

EVENTO:
{solicitacao.nome_evento}

DATA:
{solicitacao.data_evento.strftime('%d/%m/%Y')}

STATUS:
{solicitacao.get_status_display()}

Guarde este protocolo para futuras consultas.

PMBA - Uma força a serviço do cidadão.
"""

    try:
        send_mail(
            "Solicitação de Evento Recebida",
            mensagem,
            settings.DEFAULT_FROM_EMAIL,
            [solicitacao.email],
            fail_silently=True,
        )
    except Exception:
        pass


# =====================================================
# CONSULTA
# =====================================================

def consultar_protocolo(request):
    protocolo = request.GET.get("protocolo", "").strip().upper()
    solicitacao = None
    erro = None

    if protocolo:
        solicitacao = (
            Solicitacao.objects
            .select_related("municipio", "unidade", "bairro", "tipo_evento")
            .filter(protocolo=protocolo)
            .first()
        )

        if not solicitacao:
            erro = "Protocolo não encontrado."

    eventos_hoje = (
        Solicitacao.objects
        .filter(data_evento=timezone.localdate(), status="APROVADA")
        .select_related("municipio", "unidade", "bairro")
        .order_by("hora_inicio", "nome_evento")
    )

    return render(
        request,
        "solicitacoes/consultar.html",
        {
            "solicitacao": solicitacao,
            "erro": erro,
            "eventos_hoje": eventos_hoje,
        },
    )


# =====================================================
# CORREÇÃO DE SOLICITAÇÃO
# =====================================================

def corrigir_solicitacao(request, protocolo):
    solicitacao = get_object_or_404(
        Solicitacao,
        protocolo=protocolo,
    )

    if solicitacao.status != "CORRECAO":
        messages.error(
            request,
            "Esta solicitação não está disponível para correção.",
        )
        return redirect("consultar")

    if request.method == "POST":
        form = CorrecaoSolicitacaoForm(
            request.POST,
            request.FILES,
            instance=solicitacao,
        )

        if form.is_valid():
            obj = form.save(commit=False)
            obj.protocolo = solicitacao.protocolo
            obj.data_evento = solicitacao.data_evento
            obj.status = "PENDENTE"
            obj.save()

            messages.success(
                request,
                "Correções enviadas com sucesso. Sua solicitação será analisada novamente.",
            )
            return redirect("consultar")
    else:
        form = CorrecaoSolicitacaoForm(instance=solicitacao)

    return render(
        request,
        "solicitacoes/corrigir.html",
        {
            "form": form,
            "solicitacao": solicitacao,
        },
    )


# =====================================================
# GESTÃO
# =====================================================

@login_required
def agenda_gestao(request):
    hoje = timezone.localdate()

    eventos = (
        Solicitacao.objects
        .filter(
            status__in=["APROVADA", "CORRECAO"],
            data_evento__lt=hoje,
        )
        .select_related("municipio", "unidade", "bairro")
        .order_by("-data_evento", "-hora_inicio")
    )

    dia = request.GET.get("dia")
    if dia:
        try:
            eventos = eventos.filter(data_evento=date.fromisoformat(dia))
        except ValueError:
            dia = ""

    mes = request.GET.get("mes")
    if mes:
        try:
            eventos = eventos.filter(data_evento__month=int(mes))
        except (TypeError, ValueError):
            mes = ""

    ano = request.GET.get("ano")
    if ano:
        try:
            eventos = eventos.filter(data_evento__year=int(ano))
        except (TypeError, ValueError):
            ano = ""

    anos = [
        item.year
        for item in (
            Solicitacao.objects
            .filter(
                status__in=["APROVADA", "CORRECAO"],
                data_evento__lt=hoje,
            )
            .dates("data_evento", "year", order="DESC")
        )
    ]

    return render(
        request,
        "gestao/agenda.html",
        {
            "eventos": eventos,
            "anos": anos,
            "filtro_dia": dia,
            "filtro_mes": mes,
            "filtro_ano": ano,
        },
    )


@login_required
def proximos_eventos_gestao(request):
    eventos = (
        Solicitacao.objects
        .filter(
            status__in=["APROVADA", "CORRECAO"],
            data_evento__gte=timezone.localdate(),
        )
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    return render(
        request,
        "gestao/proximos_eventos.html",
        {"eventos": eventos},
    )


@login_required
def listar_pendentes_opo(request):
    solicitacoes = (
        Solicitacao.objects
        .filter(status="PENDENTE")
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    return render(
        request,
        "gestao/aprovacoes.html",
        {"solicitacoes": solicitacoes},
    )
