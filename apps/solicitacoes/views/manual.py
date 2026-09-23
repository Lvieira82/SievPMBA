from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.solicitacoes.models import (
    AnexoOPO,
    Bairro,
    DocumentoSolicitacao,
    HistoricoSolicitacao,
    Solicitacao,
    TipoDocumento,
    TipoEvento,
)
from apps.solicitacoes.pdf_security import validar_pdf_upload
from apps.solicitacoes.permissoes import pode_lancamento_manual
from .geracao_opo import _gerar_pdf_opo
from .operacional import GestaoManualForm


TIPOS_EVENTO_MANUAL = {
    "ORDINÁRIO": "Emprego ordinário de policiamento.",
    "EXTRAORDINÁRIO": "Emprego extraordinário de policiamento.",
}


def _preparar_bairros(form, municipio_id):
    if municipio_id:
        form.fields["bairro"].queryset = Bairro.objects.filter(
            municipio_id=municipio_id,
            ativo=True,
        ).order_by("nome")
    else:
        form.fields["bairro"].queryset = Bairro.objects.none()


def _preparar_formulario(form, municipio_id=None):
    """Prepara o lançamento interno com os dois tipos oficiais de evento."""
    tipos_ids = []
    for nome, descricao in TIPOS_EVENTO_MANUAL.items():
        tipo, _ = TipoEvento.objects.get_or_create(
            nome=nome,
            defaults={"descricao": descricao, "ativo": True},
        )
        if not tipo.ativo:
            tipo.ativo = True
            tipo.descricao = descricao
            tipo.save(update_fields=["ativo", "descricao"])
        tipos_ids.append(tipo.pk)

    if "tipo_evento" in form.fields:
        form.fields["tipo_evento"].required = True
        form.fields["tipo_evento"].queryset = TipoEvento.objects.filter(
            pk__in=tipos_ids,
            ativo=True,
        ).order_by("nome")
        form.fields["tipo_evento"].label = "Tipo de evento"
        form.fields["tipo_evento"].empty_label = "Selecione o tipo de evento"
        form.fields["tipo_evento"].widget.attrs.update({"class": "form-select"})

    _preparar_bairros(form, municipio_id)


def _enviar_email_recebimento_interno_festivo(solicitacao):
    """Envia o mesmo e-mail de recebimento da solicitação externa, somente para OPO Festiva."""
    if solicitacao.tipo_opo != "FESTIVO":
        return
    if not solicitacao.email:
        raise ValueError("A solicitação não possui e-mail para confirmação.")

    mensagem = f"""Olá, {solicitacao.solicitante}!

Sua solicitação foi recebida com sucesso.

PROTOCOLO: {solicitacao.protocolo}
EVENTO: {solicitacao.nome_evento}
DATA: {solicitacao.data_evento.strftime('%d/%m/%Y')}
STATUS: {solicitacao.get_status_display()}

Guarde este protocolo para futuras consultas.

PMBA - Uma força a serviço do cidadão.
"""
    send_mail(
        "Solicitação de Evento Recebida",
        mensagem,
        settings.DEFAULT_FROM_EMAIL,
        [solicitacao.email],
        fail_silently=False,
    )


def _salvar_anexos_manuais(request, solicitacao):
    """Salva quantos anexos opcionais forem adicionados, cada um com seu próprio tipo."""
    arquivos = request.FILES.getlist("anexos_manuais")
    tipos = request.POST.getlist("tipo_documento_manual")

    if not arquivos:
        return 0

    if len(tipos) != len(arquivos):
        raise ValueError("Confira o tipo e o arquivo de cada documento complementar.")

    quantidade = 0
    for tipo_id, arquivo in zip(tipos, arquivos):
        tipo_id = (tipo_id or "").strip()
        if not tipo_id:
            raise ValueError("Selecione o tipo de cada documento complementar.")

        # O formulário manual usa códigos textuais para manter todas as opções
        # disponíveis no mesmo padrão do formulário externo. Só tentamos consultar
        # por PK quando o valor recebido é realmente numérico.
        tipo = None
        if tipo_id.isdigit():
            tipo = TipoDocumento.objects.filter(pk=int(tipo_id), ativo=True).first()

        if not tipo:
            nomes_tipos = {
                "BOMBEIRO": "Corpo de Bombeiros",
                "VIGILANCIA_SANITARIA": "Vigilância Sanitária",
                "MEIO_AMBIENTE": "Meio Ambiente",
                "MINISTERIO_PUBLICO": "Ministério Público",
                "TAC": "TAC",
                "CREA": "CREA",
                "CRM": "CRM",
                "CRMV": "CRMV",
                "CRO": "CRO",
                "IBAMA": "IBAMA",
                "INEMA": "INEMA",
                "PREFEITURA": "Prefeitura",
                "POLICIA_CIVIL": "Polícia Civil",
                "EXERCITO_BRASILEIRO": "Exército Brasileiro",
                "MARINHA_DO_BRASIL": "Marinha do Brasil",
                "PRF": "PRF",
                "DETRAN": "DETRAN",
                "DEFESA_CIVIL": "Defesa Civil",
                "ANAC": "ANAC",
                "DNIT": "DNIT",
                "DERBA_SIT": "DERBA / SIT",
                "OUTRO_DOCUMENTO": "Outro Documento",
            }
            nome_tipo = nomes_tipos.get(tipo_id)
            if not nome_tipo:
                raise ValueError("Um dos tipos de documento selecionados é inválido.")
            tipo = TipoDocumento.objects.filter(nome__iexact=nome_tipo).first()
            if not tipo:
                tipo = TipoDocumento.objects.create(
                    nome=nome_tipo,
                    descricao=nome_tipo,
                    extensoes_permitidas="pdf",
                    ativo=True,
                )
            elif not tipo.ativo:
                tipo.ativo = True
                tipo.save(update_fields=["ativo"])

        validar_pdf_upload(arquivo)
        DocumentoSolicitacao.objects.create(
            solicitacao=solicitacao,
            tipo_documento=tipo,
            descricao="Anexo do lançamento interno",
            arquivo=arquivo,
        )
        quantidade += 1

    return quantidade


def _salvar_oficio_origem(request, solicitacao):
    # O formulário manual possui o campo específico "oficio_origem" e também
    # mantém o campo herdado "oficio_comandante". Aceitamos os dois nomes para
    # garantir que o PDF efetivamente anexado seja gravado em DocumentoSolicitacao
    # e, portanto, seja recuperado pela aba Documentação/OPOs Geradas.
    oficio = request.FILES.get("oficio_origem") or request.FILES.get("oficio_comandante")
    if not oficio:
        return False

    validar_pdf_upload(oficio)
    tipo_oficio, _ = TipoDocumento.objects.get_or_create(
        nome="Ofício ao Comandante",
        defaults={
            "descricao": "Ofício ao Comandante da Unidade",
            "extensoes_permitidas": "pdf",
            "ativo": True,
        },
    )
    if not tipo_oficio.ativo:
        tipo_oficio.ativo = True
        tipo_oficio.save(update_fields=["ativo"])

    DocumentoSolicitacao.objects.create(
        solicitacao=solicitacao,
        tipo_documento=tipo_oficio,
        descricao="Ofício ao Comandante da Unidade",
        arquivo=oficio,
    )
    return True


@login_required
def lancamento_manual(request):
    if not pode_lancamento_manual(request.user):
        messages.error(request, "O lançamento interno é exclusivo do Gestor e dos Membros da Unidade.")
        return redirect("painel_gestao")

    perfil = getattr(request.user, "perfil_siev", None)
    protocolo = (request.GET.get("protocolo_origem") or "").strip().upper()
    original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None
    tipos_documento = TipoDocumento.objects.filter(ativo=True).order_by("nome")

    if protocolo and not original:
        messages.error(request, "Protocolo não encontrado.")

    if request.method == "POST":
        protocolo = (request.POST.get("protocolo_origem") or "").strip().upper()
        original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None
        form = GestaoManualForm(request.POST, request.FILES, instance=original, perfil=perfil)
        _preparar_formulario(form, request.POST.get("municipio"))

        if form.is_valid():
            try:
                with transaction.atomic():
                    obj = form.save(commit=False)
                    obj.usuario = request.user
                    obj.municipio = form.cleaned_data["municipio"]
                    obj.bairro = form.cleaned_data.get("bairro")
                    obj.tipo_evento = form.cleaned_data["tipo_evento"]
                    obj.unidade = form.cleaned_data["unidade"]
                    obj.origem = "MANUAL"
                    obj.status = "APROVADA"
                    obj.aprovado_por = request.user.get_full_name() or request.user.username
                    obj.data_aprovacao = timezone.now()
                    obj.save()

                    oficio_origem = _salvar_oficio_origem(request, obj)
                    quantidade_anexos = _salvar_anexos_manuais(request, obj)

                    # Festivo segue o mesmo e-mail de recebimento da solicitação externa.
                    # Institucional permanece fora deste fluxo.
                    _enviar_email_recebimento_interno_festivo(obj)

                    HistoricoSolicitacao.objects.create(
                        solicitacao=obj,
                        usuario=request.user,
                        acao="lançamento interno",
                        observacao=(
                            "Solicitação criada/atualizada pelo Gestor ou Membro da Unidade "
                            "no lançamento interno."
                        ),
                    )

                    evento_extra = obj.tipo_evento.nome.strip().upper() == "EXTRAORDINÁRIO"
                    conteudo = _gerar_pdf_opo(
                        request,
                        obj,
                        evento_extra=evento_extra,
                    )
                    nome_arquivo = f"OPO_{obj.protocolo}.pdf"

                    AnexoOPO.objects.filter(
                        solicitacao=obj,
                        descricao__icontains="lançamento interno",
                    ).delete()

                    anexo = AnexoOPO(
                        solicitacao=obj,
                        descricao=(
                            "OPO gerada pelo lançamento interno — Tipo de evento: "
                            f"{obj.tipo_evento.nome}"
                        ),
                    )
                    anexo.arquivo.save(nome_arquivo, ContentFile(conteudo), save=True)

                    HistoricoSolicitacao.objects.create(
                        solicitacao=obj,
                        usuario=request.user,
                        acao="OPO GERADA",
                        observacao=(
                            f"OPO {nome_arquivo} gerada imediatamente pelo lançamento interno. "
                            f"Tipo de evento: {obj.tipo_evento.nome}."
                        ),
                    )

                if quantidade_anexos or oficio_origem:
                    partes = []
                    if oficio_origem:
                        partes.append("ofício de origem incluído")
                    if quantidade_anexos:
                        partes.append(f"{quantidade_anexos} anexo(s) incluído(s)")
                    messages.success(
                        request,
                        f"lançamento interno salvo, {' e '.join(partes)} e OPO {obj.protocolo} gerada imediatamente.",
                    )
                else:
                    messages.success(
                        request,
                        f"lançamento interno salvo e OPO {obj.protocolo} gerada imediatamente.",
                    )
                return redirect("detalhe_opo", id=obj.id)
            except Exception as exc:
                print("ERRO NO lançamento interno:", repr(exc))
                messages.error(
                    request,
                    f"Não foi possível concluir o lançamento interno: {exc}",
                )
    else:
        form = GestaoManualForm(instance=original, perfil=perfil)
        _preparar_formulario(form, original.municipio_id if original else None)

    return render(
        request,
        "gestao/lancamento_manual.html",
        {
            "form": form,
            "solicitacao_original": original,
            "protocolo_origem": protocolo,
            "tipos_documento": tipos_documento,
        },
    )
