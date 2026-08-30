from datetime import date
import unicodedata

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CorrecaoSolicitacaoForm, SolicitacaoForm
from .models import (
    Bairro,
    DocumentoSolicitacao,
    Municipio,
    PerfilUsuario,
    Solicitacao,
    TipoDocumento,
    Unidade,
)
from .pdf_security import validar_pdf_upload
from .territorio import (
    bairros_do_municipio,
    lista_bairros as lista_bairros_api,
    municipio_tem_multiplas_unidades,
    unidades_do_municipio,
    validar_direcionamento,
)


def portal(request):
    return render(request, "portal.html")


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
    unidades = Unidade.objects.filter(cpr_id=cpr_id, ativo=True).order_by("nome")
    return JsonResponse(
        [{"id": unidade.id, "nome": unidade.nome} for unidade in unidades],
        safe=False,
    )


def lista_municipios(request):
    termo = request.GET.get("q", "").strip()
    municipios = Municipio.objects.filter(
        nome__icontains=termo,
        ativo=True,
    ).order_by("nome")[:20]

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
    municipio = Municipio.objects.filter(id=municipio_id, ativo=True).first()

    if not municipio:
        messages.error(request, "Selecione um município antes de continuar.")
        return redirect("portal")

    if request.method == "POST":
        form = SolicitacaoForm(request.POST, request.FILES)
        form.fields.pop("origem", None)
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
                    solicitacao.origem = "EXTERNA"
                    solicitacao.status = "PENDENTE"
                    solicitacao.save()

                    _salvar_documentos(request, solicitacao)
                    _enviar_email_recebimento(solicitacao)

                    return render(
                        request,
                        "solicitacoes/sucesso.html",
                        {"protocolo": solicitacao.protocolo},
                    )
    else:
        initial = {}
        bairro_id = request.GET.get("bairro")

        if bairro_id and Bairro.objects.filter(
            id=bairro_id,
            municipio=municipio,
            ativo=True,
        ).exists():
            initial["bairro"] = bairro_id

        form = SolicitacaoForm(initial=initial)
        form.fields.pop("origem", None)

    return _render_nova(request, form, municipio)


def _obter_tipo_documento(nome, criar=False):
    """Resolve nomes antigos/códigos do formulário para TipoDocumento do banco."""
    if not nome:
        return None

    valor = str(nome).strip()
    aliases = {
        "BOMBEIRO": "Bombeiro",
        "BOMBEIROS": "Bombeiro",
        "SANITARIO": "Sanitário",
        "SANITÁRIO": "Sanitário",
        "MEIO_AMBIENTE": "Meio Ambiente",
        "MEIO AMBIENTE": "Meio Ambiente",
        "MP": "Ministério Público",
        "TAC": "TAC",
        "CREA": "CREA",
        "CRM": "CRM",
        "CRMV": "CRMV",
        "CRO": "CRO",
        "IBAMA": "IBAMA",
        "INEMA": "INEMA",
        "PREFEITURA": "Prefeitura",
        "POLICIA_CIVIL": "Polícia Civil",
        "EXERCITO": "Exército Brasileiro",
        "MARINHA": "Marinha do Brasil",
        "ANAC": "ANAC",
        "DNIT": "DNIT",
        "DERBA": "DERBA / SIT",
        "OUTRO": "Outro",
        "OUTRO DOCUMENTO": "Outro",
        "OFICIO_COMANDANTE": "Ofício ao Comandante",
        "OFÍCIO_COMANDANTE": "Ofício ao Comandante",
    }
    nome_banco = aliases.get(valor.upper(), valor)
    tipo = TipoDocumento.objects.filter(nome__iexact=nome_banco, ativo=True).first()

    if tipo:
        return tipo

    if criar:
        return TipoDocumento.objects.create(nome=nome_banco, ativo=True)

    return None


def _salvar_documentos(request, solicitacao):
    """Persiste TODOS os PDFs enviados na tabela DocumentoSolicitacao."""
    oficio = request.FILES.get("oficio_comandante")

    if oficio:
        try:
            validar_pdf_upload(oficio)
            tipo = _obter_tipo_documento("OFICIO_COMANDANTE", criar=True)
            DocumentoSolicitacao.objects.create(
                solicitacao=solicitacao,
                tipo_documento=tipo,
                descricao="Ofício ao Comandante da Unidade",
                arquivo=oficio,
            )
        except Exception as erro:
            messages.error(request, f"Ofício rejeitado: {erro}")

    tipos = request.POST.getlist("tipo_documento")
    descricoes = request.POST.getlist("descricao_documento")
    arquivos = request.FILES.getlist("documentos")

    for indice, arquivo in enumerate(arquivos):
        if not arquivo:
            continue

        try:
            validar_pdf_upload(arquivo)
        except Exception as erro:
            messages.error(request, f"Documento rejeitado: {erro}")
            continue

        tipo_nome = tipos[indice] if indice < len(tipos) else ""
        descricao = descricoes[indice] if indice < len(descricoes) else ""
        tipo = _obter_tipo_documento(tipo_nome, criar=False)

        if not tipo:
            messages.error(
                request,
                f"Tipo de documento não cadastrado: {tipo_nome or 'não informado'}.",
            )
            continue

        DocumentoSolicitacao.objects.create(
            solicitacao=solicitacao,
            tipo_documento=tipo,
            descricao=descricao.strip(),
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


def consultar_protocolo(request):
    protocolo = request.GET.get("protocolo", "").strip().upper()
    solicitacao = None
    erro = None

    if protocolo:
        solicitacao = (
            Solicitacao.objects
            .select_related("municipio", "unidade", "bairro", "tipo_evento")
            .prefetch_related("documentos__tipo_documento")
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


def corrigir_solicitacao(request, protocolo):
    solicitacao = get_object_or_404(
        Solicitacao.objects
        .select_related("municipio", "unidade", "bairro", "tipo_evento")
        .prefetch_related("documentos__tipo_documento"),
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

            _salvar_documentos(request, obj)

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
        {"form": form, "solicitacao": solicitacao},
    )


def _solicitacoes_do_gestor(request, queryset):
    """Aplica o escopo territorial definido no PerfilUsuario."""
    if request.user.is_superuser:
        return queryset

    try:
        perfil = request.user.perfil_siev
    except PerfilUsuario.DoesNotExist:
        return queryset.none()

    if not perfil.ativo:
        return queryset.none()

    if perfil.perfil == "UNIDADE":
        if not perfil.unidade_id:
            return queryset.none()
        return queryset.filter(unidade_id=perfil.unidade_id)

    if perfil.perfil == "CPR":
        if not perfil.cpr_id:
            return queryset.none()
        return queryset.filter(unidade__cpr_id=perfil.cpr_id)

    if perfil.perfil == "COPPM":
        return queryset.filter(unidade__cpr__coppm_id=perfil.cpr_id) if perfil.cpr_id else queryset.none()

    return queryset.none()


@login_required
def agenda_gestao(request):
    hoje = timezone.localdate()
    eventos = (
        Solicitacao.objects
        .filter(status__in=["APROVADA", "CORRECAO"], data_evento__lt=hoje)
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
            .filter(status__in=["APROVADA", "CORRECAO"], data_evento__lt=hoje)
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
        .filter(status__in=["APROVADA", "CORRECAO"], data_evento__gte=timezone.localdate())
        .select_related("municipio", "unidade", "bairro")
        .order_by("data_evento", "hora_inicio")
    )

    return render(request, "gestao/proximos_eventos.html", {"eventos": eventos})


@login_required
def listar_pendentes_opo(request):
    solicitacoes = (
        Solicitacao.objects
        .filter(status="PENDENTE")
        .select_related("municipio", "unidade", "bairro")
        .prefetch_related("documentos__tipo_documento")
        .order_by("data_evento", "hora_inicio")
    )

    solicitacoes = _solicitacoes_do_gestor(request, solicitacoes)

    return render(
        request,
        "gestao/aprovacoes.html",
        {"solicitacoes": solicitacoes},
    )