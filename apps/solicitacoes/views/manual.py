from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.solicitacoes.models import Bairro, HistoricoSolicitacao, Solicitacao
from .operacional import GestaoManualForm


def _preparar_bairros(form, municipio_id):
    if municipio_id:
        form.fields["bairro"].queryset = Bairro.objects.filter(
            municipio_id=municipio_id,
            ativo=True,
        ).order_by("nome")
    else:
        form.fields["bairro"].queryset = Bairro.objects.none()


@login_required
def lancamento_manual(request):
    perfil = getattr(request.user, "perfil_siev", None)
    protocolo = (request.GET.get("protocolo_origem") or "").strip().upper()
    original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None

    if request.method == "POST":
        protocolo = (request.POST.get("protocolo_origem") or "").strip().upper()
        original = Solicitacao.objects.filter(protocolo=protocolo).first() if protocolo else None
        form = GestaoManualForm(request.POST, request.FILES, instance=original, perfil=perfil)
        _preparar_bairros(form, request.POST.get("municipio"))

        if form.is_valid():
            obj = form.save(commit=False)
            obj.usuario = request.user
            obj.municipio = form.cleaned_data["municipio"]
            obj.bairro = form.cleaned_data.get("bairro")
            obj.tipo_evento = form.cleaned_data.get("tipo_evento")
            obj.unidade = form.cleaned_data["unidade"]
            obj.origem = "MANUAL"
            obj.status = "PENDENTE"
            obj.save()
            HistoricoSolicitacao.objects.create(
                solicitacao=obj,
                usuario=request.user,
                acao="LANÇAMENTO MANUAL",
                detalhes="Solicitação criada/atualizada pelo módulo de lançamento manual.",
            )
            messages.success(request, f"Informação salva com o protocolo {obj.protocolo}.")
            return redirect("documentos_solicitacao", id=obj.id)
    else:
        form = GestaoManualForm(instance=original, perfil=perfil)
        _preparar_bairros(form, original.municipio_id if original else None)

    return render(request, "gestao/lancamento_manual.html", {
        "form": form,
        "solicitacao_original": original,
        "protocolo_origem": protocolo,
    })
