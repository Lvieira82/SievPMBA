import base64
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from qrcode import make as make_qr
from weasyprint import HTML

from apps.solicitacoes.models import AnexoOPO, HistoricoSolicitacao, Solicitacao
from apps.solicitacoes.permissoes import pode_gerar_opo


def _gerar_pdf_opo(request, solicitacao, evento_extra=False, unidade_executor=None):
    """Gera o PDF da OPO usando o modelo visual operacional do SiEv95.3."""
    data_geracao = timezone.localtime()

    url_verificacao = request.build_absolute_uri(
        f"/verificar/{solicitacao.protocolo}/"
    )

    qr_img = make_qr(url_verificacao)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_base64 = "data:image/png;base64," + base64.b64encode(
        qr_buffer.getvalue()
    ).decode("utf-8")

    efetivo = (
        "Efetivo extraordinário escalado."
        if evento_extra
        else "01 (uma) Guarnição a critério do Coordenador de Área."
    )

    html = render_to_string(
        "solicitacoes/opo_pdf.html",
        {
            "solicitacao": solicitacao,
            "data_geracao": data_geracao,
            "qr_base64": qr_base64,
            "url_verificacao": url_verificacao,
            "efetivo_opo": efetivo,
            "gerado_por_nome": request.user.get_full_name() or request.user.username,
            "unidade_executor": unidade_executor,
        },
        request=request,
    )

    return HTML(
        string=html,
        base_url=request.build_absolute_uri("/"),
    ).write_pdf()


@login_required
def gerar_opo_com_evento_extra(request, id):
    solicitacao = get_object_or_404(
        Solicitacao.objects.select_related(
            "unidade", "municipio", "bairro", "tipo_evento"
        ),
        pk=id,
    )

    if not pode_gerar_opo(request.user, solicitacao):
        messages.error(request, "Você não possui permissão para gerar esta OPO.")
        return redirect("painel_gestao")

    if solicitacao.status not in {"APROVADA", "CONCLUIDA"}:
        messages.error(
            request,
            "A OPO somente pode ser gerada após a aprovação da solicitação.",
        )
        return redirect("aprovacoes")

    if request.method == "GET":
        return render(
            request,
            "gestao/gerar_opo.html",
            {"solicitacao": solicitacao},
        )

    evento_extra = request.POST.get("evento_extra") == "SIM"
    conteudo = _gerar_pdf_opo(request, solicitacao, evento_extra=evento_extra)
    nome = f"OPO_{solicitacao.protocolo}.pdf"

    anexo = AnexoOPO.objects.create(
        solicitacao=solicitacao,
        descricao=(
            "OPO gerada pelo SiEv — Evento extra: "
            f"{'SIM' if evento_extra else 'NÃO'}"
        ),
    )
    anexo.arquivo.save(nome, ContentFile(conteudo), save=True)

    HistoricoSolicitacao.objects.create(
        solicitacao=solicitacao,
        usuario=request.user,
        acao="OPO GERADA",
        observacao=(
            f"Arquivo {nome} gerado. Evento extra: "
            f"{'SIM' if evento_extra else 'NÃO'}."
        ),
    )

    messages.success(
        request,
        f"OPO {solicitacao.protocolo} gerada com sucesso.",
    )
    return redirect("detalhe_opo", id=id)
