import uuid
from datetime import datetime, timedelta

from django import forms
from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import SolicitacaoForm
from .models import Solicitacao, DocumentoSolicitacao, TipoDocumento, Municipio, Bairro, Unidade
from .leitor_multidatas import detectar_datas_oficio
from .pdf_security import validar_pdf_upload
from .territorio import bairros_do_municipio, municipio_tem_multiplas_unidades, validar_direcionamento


SESSION_DADOS = "solicitacao_multiplas_dados"
SESSION_ARQUIVOS = "solicitacao_multiplas_arquivos"
SESSION_DATAS = "solicitacao_multiplas_datas"

TEMPLATE_FORMULARIO = "solicitacoes/form_nova_solicitacao.html"
TEMPLATE_CONFIRMAR = "solicitacoes/confirmar_datas.html"


class SolicitacaoMultiplasForm(SolicitacaoForm):
    """Mesmo formulário público, mas sem executar OCR no clean()."""

    if "oficio_comandante" not in SolicitacaoForm.base_fields:
        oficio_comandante = forms.FileField(
            label="Ofício ao Comandante da Unidade (PDF)",
            required=True,
            validators=[validar_pdf_upload],
            widget=forms.FileInput(attrs={
                "class": "form-control",
                "accept": ".pdf,application/pdf",
            }),
        )

    def clean(self):
        # O OCR ocorre somente depois que os dados e arquivos já foram
        # guardados temporariamente, respeitando a arquitetura do novo fluxo.
        return forms.ModelForm.clean(self)


def _datas_validas(datas):
    hoje = timezone.localdate()
    limite = hoje + timedelta(days=3)
    unicas = {}
    for item in datas:
        data = item["data"]
        if data >= limite:
            unicas[data] = item
    return sorted(unicas.values(), key=lambda item: item["data"])


def _limpar_arquivos_temporarios(arquivos):
    for item in (arquivos or []):
        caminho = item.get("caminho") if isinstance(item, dict) else item
        if caminho:
            try:
                default_storage.delete(caminho)
            except Exception as erro:
                print("ERRO AO REMOVER ARQUIVO TEMPORÁRIO:", repr(erro))


def _limpar_sessao(request):
    for chave in (SESSION_DADOS, SESSION_ARQUIVOS, SESSION_DATAS):
        request.session.pop(chave, None)
    request.session.modified = True


def _guardar_arquivos_temporarios(request):
    pasta = f"temp_multiplas/{uuid.uuid4().hex}"
    arquivos = []
    try:
        oficio = request.FILES.get("oficio_comandante")
        if oficio:
            validar_pdf_upload(oficio)
            caminho = default_storage.save(
                f"{pasta}/oficio_comandante.pdf",
                ContentFile(oficio.read()),
            )
            oficio.seek(0)
            arquivos.append({"campo": "oficio_comandante", "caminho": caminho})

        tipos = request.POST.getlist("tipo_documento")
        descricoes = request.POST.getlist("descricao_documento")
        documentos = request.FILES.getlist("documentos")
        for indice, arquivo in enumerate(documentos):
            if not arquivo:
                continue
            validar_pdf_upload(arquivo)
            caminho = default_storage.save(
                f"{pasta}/documento_{indice}.pdf",
                ContentFile(arquivo.read()),
            )
            arquivo.seek(0)
            arquivos.append({
                "campo": "documentos",
                "caminho": caminho,
                "tipo": tipos[indice] if indice < len(tipos) else "",
                "descricao": descricoes[indice] if indice < len(descricoes) else "",
            })
    except Exception:
        _limpar_arquivos_temporarios(arquivos)
        raise
    return arquivos


def _dados_para_sessao(cleaned_data, municipio, unidade):
    dados = {}
    model_field_names = {f.name for f in Solicitacao._meta.fields}
    for campo, valor in cleaned_data.items():
        if campo == "oficio_comandante" or campo not in model_field_names:
            continue
        if campo in ("data_evento", "hora_inicio", "hora_fim"):
            continue
        if hasattr(valor, "pk"):
            dados[f"{campo}_id"] = valor.pk
        else:
            dados[campo] = valor

    dados["municipio_id"] = municipio.pk
    if unidade:
        dados["unidade_id"] = unidade.pk
    dados["data_evento"] = cleaned_data["data_evento"].isoformat()
    dados["hora_inicio"] = cleaned_data["hora_inicio"].isoformat()
    dados["hora_fim"] = cleaned_data["hora_fim"].isoformat()
    dados["origem"] = "EXTERNA"
    return dados


def _criar_solicitacao(dados, data_evento, hora_inicio, hora_fim, usuario, arquivos):
    campos = dict(dados)
    campos.pop("data_evento", None)
    campos.pop("hora_inicio", None)
    campos.pop("hora_fim", None)

    solicitacao = Solicitacao(
        **campos,
        data_evento=data_evento,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
        status="PENDENTE",
        usuario=usuario,
    )
    solicitacao.save()

    for item in arquivos:
        caminho = item["caminho"]
        campo = item["campo"]
        with default_storage.open(caminho, "rb") as arquivo:
            if campo == "oficio_comandante" and any(f.name == campo for f in Solicitacao._meta.fields):
                getattr(solicitacao, campo).save("oficio_comandante.pdf", File(arquivo), save=False)
                continue

            if campo != "documentos":
                continue

            nome_tipo = (item.get("tipo") or "").strip()
            tipo = TipoDocumento.objects.filter(nome__iexact=nome_tipo, ativo=True).first()
            if not tipo:
                continue
            documento = DocumentoSolicitacao(
                solicitacao=solicitacao,
                tipo_documento=tipo,
                descricao=item.get("descricao", ""),
            )
            documento.arquivo.save(
                "documento.pdf",
                File(arquivo),
                save=True,
            )

    solicitacao.save()
    return solicitacao


def _enviar_email_recebimento(solicitacoes):
    if not solicitacoes:
        return
    primeira = solicitacoes[0]
    linhas = [
        f"Olá, {primeira.solicitante}!",
        "",
        "Sua solicitação foi recebida com sucesso.",
        "Foram gerados protocolos independentes para cada data válida:",
        "",
    ]
    for solicitacao in solicitacoes:
        linhas.extend([
            f"PROTOCOLO: {solicitacao.protocolo}",
            f"EVENTO: {solicitacao.nome_evento}",
            f"DATA: {solicitacao.data_evento.strftime('%d/%m/%Y')}",
            f"HORÁRIO: {solicitacao.hora_inicio.strftime('%H:%M')} às {solicitacao.hora_fim.strftime('%H:%M')}",
            f"STATUS: {solicitacao.status}",
            "",
        ])
    linhas.extend([
        "Cada protocolo será analisado de forma independente pela gestão.",
        "Guarde os protocolos para futuras consultas.",
        "",
        "PMBA - Uma força a serviço do cidadão.",
    ])
    try:
        send_mail(
            "Solicitações de Evento Recebidas",
            "\n".join(linhas),
            settings.DEFAULT_FROM_EMAIL,
            [primeira.email],
            fail_silently=True,
        )
    except Exception as erro:
        print("ERRO AO ENVIAR EMAIL DAS MÚLTIPLAS DATAS:", repr(erro))


def _render_form(request, form, municipio):
    multiplas = municipio_tem_multiplas_unidades(municipio)
    if "bairro" in form.fields:
        form.fields["bairro"].queryset = bairros_do_municipio(municipio)
        form.fields["bairro"].required = multiplas
    return render(request, TEMPLATE_FORMULARIO, {
        "form": form,
        "municipio": municipio,
        "multiplas_unidades": multiplas,
        "bairros": bairros_do_municipio(municipio),
    })


def nova_solicitacao(request):
    municipio_id = request.GET.get("municipio") or request.session.get("municipio_id")
    municipio = Municipio.objects.filter(id=municipio_id, ativo=True).first()
    if not municipio:
        return redirect("portal")

    if request.method != "POST":
        return _render_form(request, SolicitacaoMultiplasForm(), municipio)

    form = SolicitacaoMultiplasForm(request.POST, request.FILES)
    if "origem" in form.fields:
        form.fields.pop("origem")
    if not _configurar_form_territorial(form, municipio):
        pass

    if not form.is_valid():
        return _render_form(request, form, municipio)

    bairro = form.cleaned_data.get("bairro")
    try:
        unidade = validar_direcionamento(municipio, bairro)
    except Exception as erro:
        form.add_error("bairro", str(erro))
        return _render_form(request, form, municipio)

    if municipio_tem_multiplas_unidades(municipio) and not unidade:
        form.add_error("bairro", "O bairro selecionado ainda não possui uma unidade responsável cadastrada.")
        return _render_form(request, form, municipio)

    try:
        arquivos = _guardar_arquivos_temporarios(request)
        dados = _dados_para_sessao(form.cleaned_data, municipio, unidade)
    except Exception as erro:
        form.add_error(None, f"Não foi possível guardar temporariamente a solicitação: {erro}")
        return _render_form(request, form, municipio)

    request.session[SESSION_DADOS] = dados
    request.session[SESSION_ARQUIVOS] = arquivos
    request.session.modified = True

    data_x = form.cleaned_data["data_evento"]
    try:
        oficio = request.FILES.get("oficio_comandante")
        oficio.seek(0)
        datas_lidas = detectar_datas_oficio(oficio, data_x.year)
    except Exception as erro:
        print("ERRO AO ANALISAR OFÍCIO:", repr(erro))
        _limpar_arquivos_temporarios(arquivos)
        _limpar_sessao(request)
        form.add_error(None, "Não foi possível analisar o Ofício ao Comandante. Verifique se o PDF é válido e legível e tente novamente.")
        return _render_form(request, form, municipio)

    datas_validas = _datas_validas(datas_lidas)
    datas_detectadas = {item["data"] for item in datas_lidas}

    if data_x not in datas_detectadas:
        _limpar_arquivos_temporarios(arquivos)
        _limpar_sessao(request)
        texto = ", ".join(item["data"].strftime("%d/%m/%Y") for item in datas_lidas) or "nenhuma"
        form.add_error(None, f"A data informada no formulário não foi identificada no Ofício ao Comandante. Data(s) identificada(s): {texto}.")
        return _render_form(request, form, municipio)

    if not datas_validas:
        _limpar_arquivos_temporarios(arquivos)
        _limpar_sessao(request)
        form.add_error(None, "O Ofício não contém nenhuma data válida. Somente datas que respeitem o mínimo de 3 dias a partir de hoje podem ser aceitas.")
        return _render_form(request, form, municipio)

    if len(datas_validas) == 1:
        try:
            usuario = request.user if request.user.is_authenticated else None
            with transaction.atomic():
                solicitacao = _criar_solicitacao(
                    dados,
                    datas_validas[0]["data"],
                    form.cleaned_data["hora_inicio"],
                    form.cleaned_data["hora_fim"],
                    usuario,
                    arquivos,
                )
            _enviar_email_recebimento([solicitacao])
        finally:
            _limpar_arquivos_temporarios(arquivos)
            _limpar_sessao(request)
        return render(request, "solicitacoes/sucesso.html", {"protocolo": solicitacao.protocolo})

    request.session[SESSION_DATAS] = [item["data"].isoformat() for item in datas_validas]
    request.session.modified = True
    return redirect("confirmar_datas")


def _configurar_form_territorial(form, municipio):
    if "bairro" not in form.fields:
        return False
    bairros = bairros_do_municipio(municipio)
    multiplas = municipio_tem_multiplas_unidades(municipio)
    form.fields["bairro"].queryset = bairros
    form.fields["bairro"].required = multiplas
    return multiplas


def confirmar_multiplas(request):
    dados = request.session.get(SESSION_DADOS)
    arquivos = request.session.get(SESSION_ARQUIVOS, [])
    datas_sessao = request.session.get(SESSION_DATAS, [])
    if not dados or not datas_sessao:
        return redirect("nova_solicitacao")

    try:
        data_x = datetime.strptime(dados["data_evento"], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        _limpar_arquivos_temporarios(arquivos)
        _limpar_sessao(request)
        return redirect("nova_solicitacao")

    limite = timezone.localdate() + timedelta(days=3)
    datas = []
    for valor in datas_sessao:
        try:
            data = datetime.strptime(valor, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue
        if data >= limite:
            datas.append(data)
    datas = sorted(set(datas))

    if len(datas) < 2 or data_x not in datas:
        _limpar_arquivos_temporarios(arquivos)
        _limpar_sessao(request)
        return redirect("nova_solicitacao")

    if request.method == "GET":
        return render(request, TEMPLATE_CONFIRMAR, {
            "datas": datas,
            "data_x": data_x,
            "hora_inicio_x": dados.get("hora_inicio", ""),
            "hora_fim_x": dados.get("hora_fim", ""),
        })

    escolhidas = []
    erros = []
    for data in datas:
        iso = data.isoformat()
        hora_inicio = request.POST.get(f"hora_inicio_{iso}", "").strip()
        hora_fim = request.POST.get(f"hora_fim_{iso}", "").strip()
        if not hora_inicio or not hora_fim:
            erros.append(f"Informe o horário de início e término para {data.strftime('%d/%m/%Y')}.")
            continue
        try:
            inicio = datetime.strptime(hora_inicio, "%H:%M").time()
            fim = datetime.strptime(hora_fim, "%H:%M").time()
        except ValueError:
            erros.append(f"Horário inválido para {data.strftime('%d/%m/%Y')}.")
            continue
        escolhidas.append((data, inicio, fim))

    if erros or len(escolhidas) != len(datas):
        return render(request, TEMPLATE_CONFIRMAR, {
            "datas": datas,
            "data_x": data_x,
            "hora_inicio_x": dados.get("hora_inicio", ""),
            "hora_fim_x": dados.get("hora_fim", ""),
            "erros": erros or ["Informe os horários de todas as datas válidas."],
        })

    usuario = request.user if request.user.is_authenticated else None
    solicitacoes = []
    try:
        with transaction.atomic():
            for data, inicio, fim in escolhidas:
                solicitacoes.append(_criar_solicitacao(dados, data, inicio, fim, usuario, arquivos))
        _enviar_email_recebimento(solicitacoes)
    except Exception as erro:
        print("ERRO AO MATERIALIZAR SOLICITAÇÕES:", repr(erro))
        _limpar_arquivos_temporarios(arquivos)
        _limpar_sessao(request)
        return render(request, TEMPLATE_CONFIRMAR, {
            "datas": datas,
            "data_x": data_x,
            "hora_inicio_x": dados.get("hora_inicio", ""),
            "hora_fim_x": dados.get("hora_fim", ""),
            "erros": ["Não foi possível concluir a criação das solicitações. Tente novamente."],
        })
    finally:
        _limpar_arquivos_temporarios(arquivos)
        _limpar_sessao(request)

    return render(request, "solicitacoes/sucesso.html", {
        "protocolos": solicitacoes,
        "protocolo": solicitacoes[0].protocolo if solicitacoes else "",
    })
