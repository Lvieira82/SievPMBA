from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
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


def _adicionar_tipo_opo(form):
    """Inclui no lançamento manual o tipo da OPO, pois ela será gerada imediatamente."""
    form.fields["evento_extra"] = forms.ChoiceField(
        choices=[
            ("NAO", "ORDINÁRIO"),
            ("SIM", "EXTRAORDINÁRIO"),
        ],
        required=True,
        label="Tipo de OPO",
        widget=forms.Select(attrs={"class": "form-select"}),
    )


@login_required
def lancamento_manual(request):
    if not pode_lancamento_manual(request.user):
        messages.error(request, "O lançamento manual é exclusivo do Gestor e dos Membros da Unidade.")
        return redirect("painel_gestao")

    perfil = getattr(request.user, "perfil_siev", None)
    protocolo = (request.GET.get("protocolo_origem") or "").strip().upper()
    original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None

    if request.method == "POST":
        protocolo = (request.POST.get("protocolo_origem") or "").strip().upper()
        original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None
        form = GestaoManualForm(request.POST, request.FILES, instance=original, perfil=perfil)
        _adicionar_tipo_opo(form)
        _preparar_bairros(form, request.POST.get("municipio"))

        if form.is_valid():
            obj = form.save(commit=False)
            obj.usuario = request.user
            obj.municipio = form.cleaned_data["municipio"]
            obj.bairro = form.cleaned_data.get("bairro")
            obj.tipo_evento = form.cleaned_data.get("tipo_evento")
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

            evento_extra = form.cleaned_data["evento_extra"] == "SIM"
            conteudo = _gerar_pdf_opo(
                request,
                obj,
                evento_extra=evento_extra,
            )
            nome_arquivo = f"OPO_{obj.protocolo}.pdf"

            # Ao editar o mesmo lançamento, elimina a OPO manual anterior para evitar duplicidade.
            AnexoOPO.objects.filter(
                solicitacao=obj,
                descricao__icontains="lançamento manual",
            ).delete()

            anexo = AnexoOPO(
                solicitacao=obj,
                descricao=(
                    "OPO gerada pelo lançamento manual — Evento extra: "
                    f"{'SIM' if evento_extra else 'NÃO'}"
                ),
            )
            anexo.arquivo.save(nome_arquivo, ContentFile(conteudo), save=True)

            HistoricoSolicitacao.objects.create(
                solicitacao=obj,
                usuario=request.user,
                acao="OPO GERADA",
                observacao=(
                    f"OPO {nome_arquivo} gerada imediatamente pelo lançamento manual. "
                    f"Evento extra: {'SIM' if evento_extra else 'NÃO'}."
                ),
            )

            messages.success(
                request,
                f"Lançamento manual salvo e OPO {obj.protocolo} gerada imediatamente.",
            )
            return redirect("detalhe_opo", id=obj.id)
    else:
        form = GestaoManualForm(instance=original, perfil=perfil)
        _adicionar_tipo_opo(form)
        _preparar_bairros(form, original.municipio_id if original else None)

    return render(
        request,
        "gestao/lancamento_manual.html",
        {
            "form": form,
            "solicitacao_original": original,
            "protocolo_origem": protocolo,
        },
    )
