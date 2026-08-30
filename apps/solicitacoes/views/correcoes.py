from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.solicitacoes.models import HistoricoSolicitacao, Solicitacao


def _escopo_gestor(request):
    if request.user.is_superuser or request.user.is_staff:
        return Solicitacao.objects.all()

    perfil = getattr(request.user, "perfil_siev", None)
    if not perfil or not perfil.ativo:
        return Solicitacao.objects.none()

    if perfil.perfil == "COPPM":
        return Solicitacao.objects.all()
    if perfil.perfil == "CPR" and perfil.cpr_id:
        return Solicitacao.objects.filter(unidade__cpr_id=perfil.cpr_id)
    if perfil.perfil == "UNIDADE" and perfil.unidade_id:
        return Solicitacao.objects.filter(unidade_id=perfil.unidade_id)

    return Solicitacao.objects.none()


@login_required
def solicitar_correcao_gestao(request, id):
    escopo = _escopo_gestor(request)
    solicitacao = get_object_or_404(
        escopo.select_related("unidade"),
        pk=id,
    )

    if solicitacao.status != "PENDENTE":
        messages.error(
            request,
            "Esta solicitação não está pendente de análise.",
        )
        return redirect("aprovacoes")

    if request.method == "POST":
        motivo = request.POST.get("motivo_correcao", "").strip()

        if not motivo:
            messages.error(request, "Informe o motivo da correção.")
            return render(
                request,
                "solicitacoes/solicitar_correcao.html",
                {"solicitacao": solicitacao},
            )

        # A versão atual do SiEv não possui mais o campo motivo_correcao
        # em Solicitacao. O motivo fica no histórico, preservando a lógica
        # utilizada no fluxo institucional sem alterar a estrutura atual.
        solicitacao.status = "CORRECAO"
        solicitacao.save(update_fields=["status", "atualizado_em"])

        HistoricoSolicitacao.objects.create(
            solicitacao=solicitacao,
            usuario=request.user,
            status="CORRECAO",
            status_anterior="PENDENTE",
            status_novo="CORRECAO",
            acao="CORREÇÃO SOLICITADA",
            observacao=motivo,
        )

        link_correcao = request.build_absolute_uri(
            reverse(
                "corrigir_solicitacao",
                kwargs={"protocolo": solicitacao.protocolo},
            )
        )

        mensagem = f"""Olá, {solicitacao.solicitante}!

Sua solicitação de policiamento necessita de correção.

PROTOCOLO:
{solicitacao.protocolo}

EVENTO:
{solicitacao.nome_evento}

MOTIVO DA CORREÇÃO:
{motivo}

Para realizar a correção, acesse diretamente:
{link_correcao}

Depois de corrigir e reenviar, a solicitação voltará para análise da unidade responsável.

Atenciosamente,

Seção de Planejamento Operacional
SiEv - Sistema Inteligente de Eventos
"""

        try:
            send_mail(
                subject="Pendência na Solicitação de Ordem de Policiamento - SiEv",
                message=mensagem,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[solicitacao.email],
                fail_silently=False,
            )
            messages.success(
                request,
                "Solicitação devolvida para correção e e-mail enviado ao solicitante.",
            )
        except Exception as erro:
            print("ERRO AO ENVIAR EMAIL DE CORREÇÃO:", repr(erro))
            messages.warning(
                request,
                "Solicitação devolvida para correção, mas o e-mail não pôde ser enviado.",
            )

        return redirect("aprovacoes")

    return render(
        request,
        "solicitacoes/solicitar_correcao.html",
        {"solicitacao": solicitacao},
    )
