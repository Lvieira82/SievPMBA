from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.solicitacoes.models import AnexoOPO, Bairro, HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.permissoes import pode_lancamento_manual
from .geracao_opo import _gerar_pdf_opo
from .operacional import GestaoManualForm


def _preparar_bairros(form, municipio_id):
    if municipio_id:
        form.fields["bairro"].queryset = Bairro.objects.filter(
            municipio_id=municipio_id,
            ativo=True,
        ).order_by("nome")
    else:
        form.fields["bairro"].queryset = Bairro.objects.none()


def _preparar_formulario(form, municipio_id=None):
    """Ajusta o formulário manual sem criar um conceito separado de tipo de OPO."""
    if "tipo_evento" in form.fields:
        form.fields["tipo_evento"].required = True
        form.fields["tipo_evento"].widget.attrs.update({"class": "form-select"})
    _preparar_bairros(form, municipio_id)


@login_required
def lancamento_manual(request):
    if not pode_lancamento_manual(request.user):
        messages.error(request, "O lançamento manual é exclusivo do Gestor e dos Membros da Unidade.")
        return redirect("painel_gestao")

    perfil = getattr(request.user, "perfil_siev", None)
    protocolo = (request.GET.get("protocolo_origem") or "").strip().upper()
    original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None

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

                    HistoricoSolicitacao.objects.create(
                        solicitacao=obj,
                        usuario=request.user,
                        acao="LANÇAMENTO MANUAL",
                        observacao="Solicitação criada/atualizada pelo Gestor ou Membro da Unidade no lançamento manual.",
                    )

                    # Lançamento manual não passa por aprovação: a OPO é gerada imediatamente.
                    conteudo = _gerar_pdf_opo(
                        request,
                        obj,
                        evento_extra=False,
                    )
                    nome_arquivo = f"OPO_{obj.protocolo}.pdf"

                    AnexoOPO.objects.filter(
                        solicitacao=obj,
                        descricao__icontains="lançamento manual",
                    ).delete()

                    anexo = AnexoOPO(
                        solicitacao=obj,
                        descricao="OPO gerada pelo lançamento manual",
                    )
                    anexo.arquivo.save(nome_arquivo, ContentFile(conteudo), save=True)

                    HistoricoSolicitacao.objects.create(
                        solicitacao=obj,
                        usuario=request.user,
                        acao="OPO GERADA",
                        observacao=(
                            f"OPO {nome_arquivo} gerada imediatamente pelo lançamento manual. "
                            f"Tipo de evento: {obj.tipo_evento}."
                        ),
                    )

                messages.success(
                    request,
                    f"Lançamento manual salvo e OPO {obj.protocolo} gerada imediatamente.",
                )
                return redirect("detalhe_opo", id=obj.id)
            except Exception as exc:
                print("ERRO NO LANÇAMENTO MANUAL:", repr(exc))
                messages.error(
                    request,
                    "Não foi possível salvar o lançamento manual e gerar a OPO. "
                    "Verifique os campos informados e tente novamente.",
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
        },
    )
