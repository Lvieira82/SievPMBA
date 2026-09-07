from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
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
    """Prepara o lançamento manual com os dois tipos oficiais de evento."""
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


def _salvar_anexos_manuais(request, solicitacao):
    """Anexos são opcionais; se enviados, devem ser PDFs e usar um tipo ativo."""
    arquivos = request.FILES.getlist("anexos_manuais")
    if not arquivos:
        return 0

    tipo_id = (request.POST.get("tipo_documento_manual") or "").strip()
    if not tipo_id:
        raise ValueError("Selecione o tipo dos anexos enviados.")

    tipo = TipoDocumento.objects.filter(pk=tipo_id, ativo=True).first()
    if not tipo:
        raise ValueError("O tipo de documento selecionado é inválido.")

    for arquivo in arquivos:
        validar_pdf_upload(arquivo)
        DocumentoSolicitacao.objects.create(
            solicitacao=solicitacao,
            tipo_documento=tipo,
            descricao="Anexo do lançamento manual",
            arquivo=arquivo,
        )

    return len(arquivos)


@login_required
def lancamento_manual(request):
    if not pode_lancamento_manual(request.user):
        messages.error(request, "O lançamento manual é exclusivo do Gestor e dos Membros da Unidade.")
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

                    quantidade_anexos = _salvar_anexos_manuais(request, obj)

                    HistoricoSolicitacao.objects.create(
                        solicitacao=obj,
                        usuario=request.user,
                        acao="LANÇAMENTO MANUAL",
                        observacao=(
                            "Solicitação criada/atualizada pelo Gestor ou Membro da Unidade "
                            "no lançamento manual."
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
                        descricao__icontains="lançamento manual",
                    ).delete()

                    anexo = AnexoOPO(
                        solicitacao=obj,
                        descricao=(
                            "OPO gerada pelo lançamento manual — Tipo de evento: "
                            f"{obj.tipo_evento.nome}"
                        ),
                    )
                    anexo.arquivo.save(nome_arquivo, ContentFile(conteudo), save=True)

                    HistoricoSolicitacao.objects.create(
                        solicitacao=obj,
                        usuario=request.user,
                        acao="OPO GERADA",
                        observacao=(
                            f"OPO {nome_arquivo} gerada imediatamente pelo lançamento manual. "
                            f"Tipo de evento: {obj.tipo_evento.nome}."
                        ),
                    )

                if quantidade_anexos:
                    messages.success(
                        request,
                        f"Lançamento manual salvo, {quantidade_anexos} anexo(s) incluído(s) e "
                        f"OPO {obj.protocolo} gerada imediatamente.",
                    )
                else:
                    messages.success(
                        request,
                        f"Lançamento manual salvo e OPO {obj.protocolo} gerada imediatamente.",
                    )
                return redirect("detalhe_opo", id=obj.id)
            except Exception as exc:
                print("ERRO NO LANÇAMENTO MANUAL:", repr(exc))
                messages.error(
                    request,
                    f"Não foi possível concluir o lançamento manual: {exc}",
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
